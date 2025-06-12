from .ProblemBase import ProblemBase
from qiskit import QuantumCircuit
from random import random

class BV(ProblemBase):
    
    def __init__(self):
        name = "Bernstein-Vazirani"
        desc = "Guesses a secret number"
        super().__init__(name, desc)
    
    def makeCirc(self, qubits):
        sNum = str(bin(random.randint(0,2**qubits)))
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
        