from .ProblemBase import ProblemBase
from qiskit import QuantumCircuit
from qiskit.circuit.library import QFT
import random
from math import pi

class QPE(ProblemBase):
    
    def __init__(self):
        """
        Initializes the Quantum Phase Estimation problem with preset name and description.

        Notes:
            Overrides the abstract `__init__` from `ProblemBase`.
        """
        
        name = "Quantum Phase Estimation"
        desc = "Estimates the phase of a quantum state"
        super().__init__(name, desc)
    
    def makeCirc(self, qubits):
        """
        Create a Quantum Phase Estimation circuit with the specified number of qubits.

        Args:
            qubits (int): The number of qubits to use in the circuit.

        Returns:
            tuple[QuantumCircuit, str]: The constructed quantum circuit and
            a string revealing the secret number encoded in the circuit.

        Notes:
            This method overrides the abstract `makeCirc` method in `ProblemBase`.
        """
        qc = QuantumCircuit(qubits + 1, qubits)  # n estimation + 1 aux qubit, n classical bits

        # Prepare auxiliary qubit in |1> state
        qc.x(qubits)

        # Apply Hadamard gates to estimation qubits
        qc.h(range(qubits))

        # Generate random phase theta in [0, 2*pi)
        theta = random.uniform(0, 2 * pi)

        # Apply controlled-U operations with controlled phase rotations
        for qubit in range(qubits):
            repetitions = 2 ** (qubits - qubit - 1)
            angle = theta * repetitions  # multiply theta by power of two
            qc.cp(angle, qubit, qubits)

        # Apply inverse QFT on estimation qubits
        qc.append(QFT(qubits, inverse=True), range(qubits))

        # Measure estimation qubits
        qc.measure(range(qubits), range(qubits))

        return qc, "Phase to estimate: " + str(theta)
        