from .ProblemBase import ProblemBase
from qiskit import QuantumCircuit
from random import randint

class BV(ProblemBase):
    
    def __init__(self):
        """
        Initializes the Bernstein-Vazirani problem with preset name and description.

        Notes:
            Overrides the abstract `__init__` from `ProblemBase`.
        """
        name = "Bernstein-Vazirani"
        desc = "Guesses a secret number"
        super().__init__(name, desc)
    
    def makeCirc(self, qubits):
        """
        Create a Bernstein-Vazirani circuit with the specified number of qubits.

        Args:
            qubits (int): The number of qubits to use in the circuit.

        Returns:
            tuple[QuantumCircuit, str]: The constructed quantum circuit and
            a string revealing the secret number encoded in the circuit.

        Notes:
            This method overrides the abstract `makeCirc` method in `ProblemBase`.
        """


        sNum = str(bin(randint(0,2**qubits)))
        sNum = sNum[2:]
        if (len(sNum) < qubits):
            zStr = ''
            for i in range(qubits-len(sNum)):
                zStr = zStr + "0"
            sNum = zStr + sNum
        
        qc = QuantumCircuit(len(sNum)+1, len(sNum))

        # Apply Hadamard gates before the oracle
        qc.h(range(len(sNum)))

        # Apply the oracle
        for ii, yesno in enumerate(reversed(sNum)):
            if yesno == '1':
                qc.cx(ii, len(sNum))

        # Apply Hadamard gates after the oracle
        qc.h(range(len(sNum)))

        # Measure
        qc.measure(range(len(sNum)), range(len(sNum)))

        return qc, "Secret number: " + str(sNum)
        