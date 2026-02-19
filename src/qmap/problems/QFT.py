# src/qmap/problems/QFT.py
from .ProblemBase import ProblemBase
from qiskit import QuantumCircuit
from qiskit.circuit.library import QFT

class QuantFT(ProblemBase):
    '''A quantum fourier transformation. Child of abstract class ProblemBase.'''
    
    def __init__(self):
        """
        Initializes the Quantum Fourier Transform problem with preset name and description.

        Notes:
            Overrides the abstract `__init__` from `ProblemBase`.
        """
        name = "Quantum Fourier Transform"
        desc = "Applies quantum fourier transform to qubits"
        super().__init__(name, desc)
    
    def makeCirc(self, qubits):
        """
        Create a Quantum Fourier Transform circuit with the specified number of qubits.

        Args:
            qubits (int): The number of qubits to use in the circuit.

        Returns:
            tuple[QuantumCircuit, str]: The constructed quantum circuit and
            a string revealing the secret number encoded in the circuit.

        Notes:
            This method overrides the abstract `makeCirc` method in `ProblemBase`.
        """
        qc = QuantumCircuit(qubits, qubits)

        # Apply QFT
        qft = QFT(qubits)
        qc.append(qft, range(qubits))

        # Measure the circuit
        qc.measure(range(qubits), range(qubits))

        return qc, "Qubit Count: " + str(qubits)
        