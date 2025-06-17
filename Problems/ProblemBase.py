from qiskit.providers.backend import BackendV2
from typing import Tuple
import time
from qiskit import transpile
from qiskit.primitives import Sampler
from qiskit import QuantumCircuit

from abc import ABC, abstractmethod

class ProblemBase(ABC):

    """Abstract base class for QMAP Problems.

    This class defines the interface that all problem classes must implement.
    """

    @abstractmethod
    def __init__(self, name, desc) -> None:
        """Initializes the problem

        Args:
            name (str): The problem name.
            desc (str): The problem description.

        Notes:
            This is an abstract method and must be implemented by subclasses.
        """
        self.name = name
        self.desc = desc

    @abstractmethod
    def makeCirc(self,qubits) -> Tuple[QuantumCircuit, str]:
        """
        Abstract method to create a circuit for the relevant problem.

        Args:
            name (str): The problem name.
            desc (str): The problem description.

        Returns:
            QuantumCircuit: The circuit for the problem.
            str: relevant data from the problem.

        Note:
            This is an abstract method and must be implemented by subclasses.
        """
        pass

    def run(self, qubits, shots, backend, sampler, binRes):
        """
        Runs a circuit with varying parameters. 

        Args:
            qubits (int): The amount of qubits in the problem.
            shots (int): The shots for the problem.
            backend (): The backend to run on.
            sampler (): The sampler to run on (should have `Sampler(mode=backend)`).
            binRes (boolean): If the backend returns data in binary (True) or hexadecimal (False).

        Returns:
            Tuple [str, str, str, str]: A tuple containing:
            - bin (str): Binary circuit data.
            - data (str): Extra circuit data.
            - timestr (str): Execution time string.
            - qTime (str): IBM's `job.usage_estimation` (str), or `'N/A'` if unavailable
        """
        circ, data = self.makeCirc(qubits)

        timeStart = time.time_ns()
        transpiled_circuit = transpile(circ, backend=backend)

        if (binRes):
            job = backend.run(transpiled_circuit, shots = shots)
            
        else:
            job = sampler.run([transpiled_circuit], shots=shots)
        
        result = job.result()
        
        timeEnd = time.time_ns()

        if (type(backend) == BackendV2):
            qTime = job.usage_estimation['quantum_seconds']
        else:
            qTime = "N/A"

        if (binRes):
            samplerResult = result
            bin = samplerResult.get_counts()

        else:
            samplerResult = result[0]
            bin = samplerResult.data.c.get_counts()        

        timestr = str(timeEnd - timeStart)[:-3]
        timestr = timestr[:-3] + "." + timestr[-3:]

        return bin, data, timestr, qTime
        