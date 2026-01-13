import datetime
from typing import Tuple
import time

from qiskit import transpile
from qiskit import QuantumCircuit
from qiskit.transpiler import CouplingMap
from qiskit.providers.backend import BackendV2
from qiskit_ibm_runtime import Sampler

import qnexus as qnx
# from pytket.extensions.qiskit import qiskit_to_tk

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

            # Upload circuit to Nexus
            circ_ref = qnx.circuits.upload(
                tk_circ,
                name=f"{self.name}_{qubits}q_raw"
            )

            # Compile circuit
            compile_job = qnx.start_compile_job(
                programs=[circ_ref],
                backend_config=backend,
                optimisation_level=2,
                name=f"compile_{self.name}_{qubits}q"
            )

            # Wait for compilation to finish
            qnx.jobs.wait_for(compile_job)

            # Reference to compiled circuit 
            compiled_ref = qnx.jobs.results(compile_job)[0].get_output()

            # Submit job
            run_job = qnx.start_execute_job(
                programs=[compiled_ref],
                backend_config=backend,
                n_shots=[shots],
                name=f"run_{self.name}_{qubits}q"
            )

            # Wait for job to finish running
            qnx.jobs.wait_for(run_job)

            # Get results
            result_ref = qnx.jobs.results(run_job)[0]
            result = result_ref.download_result()
            
        else:
            
            # basis_gates, coupling_map = self.extract_backend_info(backend)

            transpiled_circuit = transpile(
                circ,
                backend=backend,
                optimization_level=3,
                # basis_gates=basis_gates,
                # coupling_map=coupling_map,
            )
            _ = transpiled_circuit.count_ops()

            if (backendType == "IBM"):
                job = sampler.run([transpiled_circuit], shots=shots)
            elif (backendType == "IQM" or backendType == "IonQ"):
                job = backend.run(transpiled_circuit, shots=shots)
            else:
                raise ValueError("Input backend does not match listed backends.")
            result = job.result()
        
        timeEnd = time.time_ns()

        # Data to report
        qTime = job.usage_estimation['quantum_seconds'] if hasattr(job, 'usage_estimation') else "N/A"
        samplerResult = result[0] if backendType == "IBM" else result
        bin = samplerResult.data.c.get_counts() if backendType == "IBM" else samplerResult.get_counts()
  
        # Try to get precise server time, fallback to client time
        end_time = None
    
        if hasattr(job, 'metrics') and 'timestamps' in job.metrics():
            end_time = job.metrics()['timestamps'].get('finished')

        if end_time is None:
            end_time = datetime.datetime.now()

        uTime = str(timeEnd - timeStart)[:-3]
        uTime = uTime[:-3] + "." + uTime[-3:]

        return bin, data, uTime, qTime, end_time
        