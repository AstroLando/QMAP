# src/qmap/problems/BV.py
from .ProblemBase import ProblemBase
from qiskit import QuantumCircuit
from random import randint

class BV(ProblemBase):
    '''An implementation of the Bernstein-Vazirani algorithm. Child of abstract class ProblemBase.'''
    
    def __init__(self):
        """
        Initializes the Bernstein-Vazirani algorithm with preset name and description.

        Notes:
            Overrides the abstract `__init__` from `ProblemBase`.
        """
        name = "Bernstein-Vazirani"
        desc = "Guesses a secret number"
        super().__init__(name, desc)
    
    def makeCirc(self, qubits):
        """
        Create a Bernstein-Vazirani algorithm circuit with the specified number of qubits.

        Args:
            qubits (int): The number of qubits to use in the circuit.

        Returns:
            tuple[QuantumCircuit, str]: The constructed quantum circuit and
            a string revealing the secret number encoded in the circuit.

        Notes:
            This method overrides the abstract `makeCirc` method in `ProblemBase`.
        """
        cbits = qubits - 1

        # Create secret string
        sNum = bin(randint(0, 2**cbits - 1))[2:].zfill(cbits)

        # Construct circuit 
        # Note: there is 1 ancilla qubit to consider in qubit count
        qc = QuantumCircuit(qubits, cbits)
        
        # Flip ancilla (last qubit)
        qc.x(cbits) 
        qc.barrier()

        # Apply Hadamard gates before the oracle
        qc.h(range(qubits))
        qc.barrier()

        # Apply the oracle
        for ii, yesno in enumerate(reversed(sNum)):
            if yesno == '1':
                qc.cx(ii, len(sNum))

        qc.barrier()

        # Apply Hadamard gates after the oracle
        qc.h(range(cbits))

        qc.barrier()

        # Measure
        qc.measure(range(cbits), range(cbits))

        return qc, "Secret number: " + str(sNum)
        