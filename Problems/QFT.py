from .ProblemBase import ProblemBase
from qiskit import QuantumCircuit
from qiskit.circuit.library import QFT

class QuantFT(ProblemBase):
    
    def __init__(self):
        name = "Quantum Fourier Transform"
        desc = "Applies quantum fourier transform to qubits"
        super().__init__(name, desc)
    
    def makeCirc(self, qubits):
        qc = QuantumCircuit(qubits, qubits)

        # Apply QFT
        qft = QFT(qubits)
        qc.append(qft, range(qubits))

        # Measure the circuit
        qc.measure(range(qubits), range(qubits))

        return qc, "Qubit Count: " + str(qubits)
        