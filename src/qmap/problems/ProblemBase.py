import datetime
from typing import Tuple
import time

from qiskit import transpile
from qiskit import QuantumCircuit
from qiskit.transpiler import CouplingMap
from qiskit.providers.backend import BackendV2
from qiskit_ibm_runtime import Sampler

import qnexus as qnx
from pytket.extensions.qiskit import qiskit_to_tk

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

        calib_data = "N/A"

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

            try:
                backend_info = result_ref.download_backend_info()
                calib_data = backend_info.to_dict() if hasattr(backend_info, 'to_dict') else str(backend_info)
            except Exception as e:
                calib_data = f"Quantinuum fetch error: {str(e)}"
            
        else:
            
            transpiled_circuit = transpile(
                circ,
                backend=backend,
                optimization_level=3
            )
            _ = transpiled_circuit.count_ops()

            calib_data = self.get_calibration_data(backend, transpiled_circuit, backendType)

            if backendType == "IBM":
                job = sampler.run([transpiled_circuit], shots=shots)
            elif backendType == "IQM":
                job = backend.run(transpiled_circuit, shots=shots)
            elif backendType == "IonQ":
                transpiled_circuit = transpile(
                    circ,
                    backend=backend,
                    optimization_level=1, # Recommended due to incompatibility of Qiskit transpile with IonQ's compiler
                )
                _ = transpiled_circuit.count_ops()

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

        end_time = end_time.isoformat(timespec='milliseconds') + "Z"

        uTime = str(timeEnd - timeStart)[:-3]
        uTime = uTime[:-3] + "." + uTime[-3:]

        # TODO: Return job ID, created time

        return bin, data, uTime, qTime, end_time, calib_data
        
    def get_calibration_data(self, backend, transpiled_circuit, backendType):
        """Extracts T1, T2, and Readout Error for the active qubits."""
        data = {}
        try:
            # Get physical qubits used in the circuit
            if hasattr(transpiled_circuit, "layout") and transpiled_circuit.layout:
                 # Map virtual -> physical. We only care about the physical indices.
                 active_qubits = transpiled_circuit.layout.final_index_layout()
            else:
                 # Fallback if no layout info (e.g. simulator or direct mapping)
                 active_qubits = range(transpiled_circuit.num_qubits)

            # IBM and IQM (Qiskit-based)
            if backendType in ["IBM", "IQM"]:
                if hasattr(backend, "properties"):
                    props = backend.properties()
                    if props:
                        for q in active_qubits:
                            # Extract key metrics
                            data[f"q{q}"] = {
                                "T1": props.t1(q),
                                "T2": props.t2(q),
                                "readout_error": props.readout_error(q)
                            }
            
            # IonQ 
            elif backendType == "IonQ":
                # IonQ usually provides average fidelity via characterization
                # If using Qiskit IonQ provider, properties() might be sparse
                if hasattr(backend, "properties"):
                     props = backend.properties()
                     if props:
                        for q in active_qubits:
                            data[f"q{q}_T1"] = props.t1(q)
                            data[f"q{q}_T2"] = props.t2(q)
                # Fallback: check target if properties failed
                if not data and hasattr(backend, "target"):
                     data["info"] = "Check backend.target for latest calibration"

        except Exception as e:
            data["error_extracting"] = str(e)
            
        return data