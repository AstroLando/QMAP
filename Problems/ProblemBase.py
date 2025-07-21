from qiskit.providers.backend import BackendV2
from typing import Tuple
import time
from qiskit import transpile
from qiskit import QuantumCircuit
from qiskit.transpiler import CouplingMap

from pytket.extensions.qiskit.qiskit_convert import qiskit_to_tk, tk_to_qiskit
from pytket.extensions.quantinuum import QuantinuumBackend

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
    
    def extract_backend_info(self, backend):
        """Extract basis gates and coupling map from a Qiskit backend (IQM, IBM, etc.)."""

        # New-style backends (BackendV2) like IQM and latest IBM devices
        if hasattr(backend, "target") and backend.target is not None:
            target = backend.target

            # Get native gate names
            basis_gates = list(target.operation_names)

            # Get CZ connectivity, or fallback to general coupling map
            if 'cz' in target.operation_names:
                cz_pairs = list(target['cz'].keys())
            else:
                # fallback: use all two-qubit ops
                two_qubit_ops = [name for name in target.operation_names if target[name].num_qubits == 2]
                cz_pairs = []
                for op in two_qubit_ops:
                    cz_pairs += list(target[op].operation_qubits)

            # Expand to symmetric if needed (Qiskit treats coupling as directed)
            cz_pairs += [(b, a) for (a, b) in cz_pairs if (b, a) not in cz_pairs]
            coupling_map = CouplingMap(couplinglist=cz_pairs)

        # Old-style backends (BackendV1, like some IBMQ simulators)
        elif hasattr(backend, "configuration"):
            config = backend.configuration()
            basis_gates = config.basis_gates
            coupling_map = CouplingMap(couplinglist=config.coupling_map)

        else:
            raise ValueError("Unsupported backend format: cannot extract gate or coupling info.")

        return basis_gates, coupling_map


    def run(self, qubits, shots, backend, sampler, backendType):
        """
        Runs a circuit with varying parameters. 

        Args:
            qubits (int): The amount of qubits in the problem.
            shots (int): The shots for the problem.
            backend (): The backend to run on.
            sampler (): The sampler to run on (should have `Sampler(mode=backend)`).
            backendType (string): Which company backend you are using.

        Returns:
            Tuple [str, str, str, str]: A tuple containing:
            - bin (str): Binary circuit data.
            - data (str): Extra circuit data.
            - timestr (str): Execution time string.
            - qTime (str): IBM's `job.usage_estimation` (str), or `'N/A'` if unavailable
        """
        circ, data = self.makeCirc(qubits)

        timeStart = time.time_ns()

        if (backendType == "Quantinuum"):
            # Compile using pytket
            tk_circ = qiskit_to_tk(circ)

            transpiled_circuit = backend.get_compiled_circuit(tk_circ)
            job = backend.process_circuit(transpiled_circuit, n_shots=1024)
            result = backend.get_result(job)
        else:
            
            basis_gates, coupling_map = self.extract_backend_info(backend)

            transpiled_circuit = transpile(
                circ,
                basis_gates=basis_gates,
                coupling_map=coupling_map,
                optimization_level=3
            )
            
            _ = transpiled_circuit.count_ops()
            if (backendType == "IBM"):
                job = sampler.run([transpiled_circuit], shots=shots)
            elif (backendType == "IQM"):
                job = backend.run(transpiled_circuit, shots=shots)
            else:
                raise ValueError("Input backend does not match listed backends.")
            result = job.result()
        
        timeEnd = time.time_ns()

        qTime = job.usage_estimation['quantum_seconds'] if backendType == "IBM" else "N/A"

        if (backendType == "IBM"):
            samplerResult = result[0]
            bin = samplerResult.data.c.get_counts()  
        else:
            samplerResult = result
            bin = samplerResult.get_counts()
  

        timestr = str(timeEnd - timeStart)[:-3]
        timestr = timestr[:-3] + "." + timestr[-3:]

        return bin, data, timestr, qTime
        