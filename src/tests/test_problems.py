# src/tests/test_problems.py
import pytest
from qiskit import QuantumCircuit

from qmap.problems.RNG import RNG
from qmap.problems.BV import BV
from qmap.problems.QFT import QuantFT
from qmap.problems.QPE import QPE
from qmap.problems.Grovers import Grovers

# Pytest parameterization lets us run the same test logic across all algorithms
@pytest.mark.parametrize("problem_class, test_qubits", [
    (RNG, 4),
    (BV, 5),
    (QuantFT, 3),
    (QPE, 4),
    (Grovers, 3)
])
def test_circuit_generation(problem_class, test_qubits):
    """
    Verifies that every algorithm correctly builds a QuantumCircuit 
    with the expected number of qubits and returns the metadata string.
    """
    problem = problem_class()
    
    # Run the circuit generator
    circ, metadata = problem.makeCirc(test_qubits)
    
    # 1. Verify we got a valid Qiskit circuit back
    assert isinstance(circ, QuantumCircuit), f"{problem.name} did not return a QuantumCircuit"
    
    # 2. Verify metadata is a string
    assert isinstance(metadata, str), f"{problem.name} metadata is not a string"
    
    # 3. Verify the qubit count matches expectations
    # QPE adds an ancilla, so its circuit size is test_qubits + 1
    expected_qubits = test_qubits + 1 if problem_class == QPE else test_qubits
    assert circ.num_qubits == expected_qubits, f"{problem.name} built with wrong qubit count"

def test_problem_runner_config_parsing():
    """
    Verifies that ProblemRunner correctly unpacks kwargs into the ProblemConfig tuple.
    """
    from qmap.problemRunner import ProblemRunner
    
    runner = ProblemRunner()
    test_problem = RNG()
    
    # Simulate **merged_cfg being passed from the YAML config
    mock_config = {
        'reps': 5,
        'minQubits': 2,
        'maxQubits': 10,
        'qubitStep': 2,
        'minShots': 100,
        'maxShots': 200,
        'shotStep': 50,
        'nickname': "Test_RNG"
    }
    
    runner.addProblem(test_problem, **mock_config)
    
    # Verify the internal array stored it correctly
    assert len(runner.problemArr) == 1
    config_obj = runner.problemArr[0]
    
    assert config_obj.instance.name == "Random Number Generator"
    assert config_obj.reps == 5
    assert config_obj.max_q == 10
    assert config_obj.nickname == "Test_RNG"