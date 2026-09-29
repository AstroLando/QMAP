# test_vqe_qool.py

import numpy as np

from scipy.optimize import minimize
from qiskit.quantum_info import Statevector

from vqe_pauli_expectation import VQEPauliExpectation


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

NUM_QUBITS = 4
LAYERS = 2
MAX_ITERATIONS = 50

# Counters for QOOL/dataflow characterization
metrics = {
    "objective_evaluations": 0,
    "qpu_calls": 0,
    "classical_sync_points": 0,
}


# ------------------------------------------------------------
# Create problem
# ------------------------------------------------------------

problem = VQEPauliExpectation(
    num_qubits=NUM_QUBITS,
    layers=LAYERS,
    shots=1024,
)

hamiltonian = problem.get_observables()


# ------------------------------------------------------------
# Quantum expectation-value kernel
# ------------------------------------------------------------

def evaluate_energy(parameters):
    """
    Represents one logical QPU invocation.

    Classical parameters are supplied to the quantum kernel,
    the parameterized state is prepared, <H> is evaluated,
    and the result is returned to the classical optimizer.
    """

    metrics["objective_evaluations"] += 1
    metrics["qpu_calls"] += 1

    # Update parameters for this objective evaluation
    problem.parameters = np.asarray(parameters)

    # Build parameter-bound circuit
    circuit = problem.build_circuit()

    # Ideal quantum execution
    state = Statevector.from_instruction(circuit)

    # Evaluate <psi|H|psi>
    energy = np.real(
        state.expectation_value(hamiltonian)
    )

    # Returning the result to the optimizer represents
    # a classical/quantum synchronization point.
    metrics["classical_sync_points"] += 1

    print(
        f"Evaluation {metrics['objective_evaluations']:3d} | "
        f"Energy = {energy:.8f}"
    )

    return energy


# ------------------------------------------------------------
# Classical outer-loop optimizer
# ------------------------------------------------------------

initial_parameters = problem.parameters.copy()

print("\nStarting QOOL/VQE optimization")
print("--------------------------------")

result = minimize(
    evaluate_energy,
    initial_parameters,
    method="COBYLA",
    options={
        "maxiter": MAX_ITERATIONS,
    },
)


# ------------------------------------------------------------
# Results
# ------------------------------------------------------------

print("\nOptimization complete")
print("--------------------------------")

print("Final energy:")
print(result.fun)

print("\nFinal parameters:")
print(result.x)

print("\nOptimizer status:")
print(result.message)


# ------------------------------------------------------------
# QOOL structural metrics
# ------------------------------------------------------------

print("\nQOOL Dataflow Metrics")
print("--------------------------------")

for key, value in metrics.items():
    print(f"{key}: {value}")

print("\nClassification")
print("--------------------------------")
print("Pattern: QOOL")
print("Locality: Fragmented")
print("Quantum role: expectation-value evaluator")
print("Classical role: outer-loop optimizer")

print(
    "\nQuantum Residency Ratio (heuristic): "
    f"{metrics['qpu_calls'] / "
    f"(metrics['qpu_calls'] + metrics['classical_sync_points']):.3f}"
)
