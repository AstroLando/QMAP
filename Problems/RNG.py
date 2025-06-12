from .ProblemBase import ProblemBase
from qiskit import QuantumCircuit

class RNG(ProblemBase):
    
    def __init__(self):
        name = "Random Number Generator"
        desc = "Creates a random number of the input qubit length (in binary)"
        super().__init__(name, desc)
    
    def makeCirc(self, qubits):
        rng = QuantumCircuit(qubits, qubits)
        for l in range(qubits):
            rng.h(l)
        for l in range(qubits):
            rng.measure(l,l)
        
        return rng, "Qubit Count: " + str(qubits)
        