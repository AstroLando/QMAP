from .ProblemBase import ProblemBase
from qiskit import QuantumCircuit
from qiskit.circuit.library import GroverOperator
import math
import random

class Grovers(ProblemBase):
    
    def __init__(self):
        """
        Initializes the Grovers Algorithm problem with preset name and description.

        Notes:
            Overrides the abstract `__init__` from `ProblemBase`.
        """
        name = "Grover's Algorithm"
        desc = "Guesses a secret number"
        super().__init__(name, desc)
    
    def makeCirc(self, qubits):
        """
        Create a Grover's algorithm circuit with the specified number of qubits.

        Args:
            qubits (int): The number of qubits to use in the circuit.

        Returns:
            tuple[QuantumCircuit, str]: The constructed quantum circuit and
            a string revealing the secret number encoded in the circuit.

        Notes:
            This method overrides the abstract `makeCirc` method in `ProblemBase`.
        """
        #optimal iterations
        iterations = int(round(math.pi / 4 * math.sqrt(2**qubits))) 

        targetBitstring = ''.join(random.choice('01') for _ in range(qubits))

        n = len(targetBitstring)
        oracle = QuantumCircuit(n)

        # Step 1: Flip qubits where target bit is '0'
        for i, bit in enumerate(reversed(targetBitstring)):
            if bit == '0':
                oracle.x(i)

        # Step 2: Multi-controlled-Z gate (flip amplitude of target)
        oracle.h(n - 1)
        if n == 1:
            oracle.z(0)
        elif n == 2:
            oracle.cz(0, 1)
        else:
            oracle.mcx(list(range(n - 1)), n - 1)
        oracle.h(n - 1)

        # Step 3: Undo flips
        for i, bit in enumerate(reversed(targetBitstring)):
            if bit == '0':
                oracle.x(i)


        grover_op = GroverOperator(oracle)

        qc = QuantumCircuit(qubits, qubits)
        qc.h(range(qubits))  # Initial superposition

        for _ in range(iterations):
            qc.append(grover_op, range(qubits))

        qc.measure(range(qubits), range(qubits))
        return qc, "Iterations: " + str(iterations) + ", Target string: " + str(targetBitstring)
        