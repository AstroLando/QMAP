# src/qmap/problems/RNG.py
from .ProblemBase import ProblemBase
from qiskit import QuantumCircuit

class RNG(ProblemBase):
    '''A quantum random number generator. Child of abstract class ProblemBase.'''
    
    def __init__(self):
        """
        Initializes the Random Number Generator problem with preset name and description.

        Notes:
            Overrides the abstract `__init__` from `ProblemBase`.
        """
        name = "Random Number Generator"
        desc = "Creates a random number of the input qubit length (in binary)"
        super().__init__(name, desc)
    
    def makeCirc(self, qubits):
        """
        Create a Random Number Generation circuit with the specified number of qubits.

        Args:
            qubits (int): The number of qubits to use in the circuit.

        Returns:
            tuple[QuantumCircuit, str]: The constructed quantum circuit and
            a string revealing the secret number encoded in the circuit.

        Notes:
            This method overrides the abstract `makeCirc` method in `ProblemBase`.
        """
        rng = QuantumCircuit(qubits, qubits)
        for l in range(qubits):
            rng.h(l)
        for l in range(qubits):
            rng.measure(l,l)
        
        return rng, "Qubit Count: " + str(qubits)
        