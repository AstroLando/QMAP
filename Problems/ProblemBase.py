from qiskit.providers.backend import BackendV2
import time
from qiskit import transpile
from qiskit.primitives import Sampler

from abc import ABC, abstractmethod

class ProblemBase(ABC):
    @abstractmethod
    def __init__(self, name, desc):
        self.name = name
        self.desc = desc

    @abstractmethod
    def makeCirc():
        pass

    def run(self, qubits, shots, backend, sampler, hexRes):
        print("hexRes", hexRes)
        circ, data = self.makeCirc(qubits)

        timeStart = time.time_ns()
        transpiled_circuit = transpile(circ, backend=backend)

        job = sampler.run([transpiled_circuit], shots=shots, options={"memory": False})
        
        result = job.result()
        
        timeEnd = time.time_ns()

        if (type(backend) == BackendV2):
            qTime = job.usage_estimation['quantum_seconds']
        else:
            qTime = "N/A"

        samplerResult = result[0]
        bin = samplerResult.data.c.get_counts()

        timestr = str(timeEnd - timeStart)[:-3]
        timestr = timestr[:-3] + "." + timestr[-3:]

        return bin, data, timestr, qTime
        