# src/qmap/problems/ProblemBase.py
import time, os, datetime
from typing import Tuple
from abc import ABC, abstractmethod

import qnexus as qnx
from pytket.extensions.qiskit import qiskit_to_tk

from qiskit import transpile
from qiskit import QuantumCircuit
from qiskit.transpiler import CouplingMap
from qiskit.providers.backend import BackendV2
from qiskit_ibm_runtime import SamplerV2 as Sampler 

class ProblemBase(ABC):
    """Abstract base class for QMAP Problems."""

    @abstractmethod
    def __init__(self, name, desc) -> None:
        self.name = name
        self.desc = desc

    @abstractmethod
    def makeCirc(self, qubits) -> Tuple[QuantumCircuit, str]:
        pass

    def run(self, qubits, shots, backend, sampler, backendType):
        """
        Runs a circuit and extracts vendor-specific server timestamps and job IDs.

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
        
        # Initialize return variables
        job_id = "N/A"
        created_time = "N/A"
        end_time = "N/A"
        qTime = "N/A"

        if (backendType == "Quantinuum"):
            tk_circ = qiskit_to_tk(circ)
            circ_ref = qnx.circuits.upload(tk_circ, name=f"{self.name}_{qubits}q_raw")

            compile_job = qnx.start_compile_job(
                programs=[circ_ref],
                backend_config=backend,
                optimisation_level=2,
                name=f"compile_{self.name}_{qubits}q"
            )
            qnx.jobs.wait_for(compile_job)
            compiled_ref = qnx.jobs.results(compile_job)[0].get_output()

            run_job = qnx.start_execute_job(
                programs=[compiled_ref],
                backend_config=backend,
                n_shots=[shots],
                name=f"run_{self.name}_{qubits}q"
            )
            
            # Capture ID before waiting
            job_id = str(run_job.id)
            qnx.jobs.wait_for(run_job)
            
            result_ref = qnx.jobs.results(run_job)[0]
            result = result_ref.download_result()
            
            # Extract Quantinuum Timestamps from Nexus
            try:
                job_df = run_job.df()
                if not job_df.empty:
                    created_time = job_df['created'].iloc[0].isoformat() if 'created' in job_df.columns else "N/A"
                    end_time = job_df['modified'].iloc[0].isoformat() if 'modified' in job_df.columns else "N/A"
            except Exception:
                created_time = "N/A"
                end_time = "N/A"

            result_ref = qnx.jobs.results(run_job)[0]
            result = result_ref.download_result()
            bin_counts = result.get_counts()

            try:
                backend_info = result_ref.download_backend_info()
                calib_data = backend_info.to_dict() if hasattr(backend_info, 'to_dict') else str(backend_info)
            except Exception as e:
                calib_data = f"Quantinuum fetch error: {str(e)}"

        else:
            # Handle Qiskit-based backends (IBM, IQM, IonQ)
            if backendType == "IonQ":
                transpiled_circuit = transpile(circ, backend=backend, optimization_level=1)
                job = backend.run(transpiled_circuit, shots=shots)
            elif backendType == "IQM":
                transpiled_circuit = transpile(circ, backend=backend, optimization_level=3)
                job = backend.run(transpiled_circuit, shots=shots)
            elif backendType == "IBM":
                transpiled_circuit = transpile(circ, backend=backend, optimization_level=3)
                job = sampler.run([transpiled_circuit], shots=shots)
            else:
                raise ValueError(f"Unsupported backendType: {backendType}")

            job_id = job.job_id()
            result = job.result()
            
            # Extraction logic for Server-Side Timestamps
            if backendType == "IBM":
                metrics = job.metrics()
                ts = metrics.get('timestamps', {})
                created_time = ts.get('created', "N/A")
                end_time = ts.get('finished', "N/A")
                qTime = job.usage_estimation.get('quantum_seconds', "N/A") if hasattr(job, 'usage_estimation') else "N/A"
                # V2 Primitive result parsing
                samplerResult = result[0]
                bin_counts = samplerResult.data.c.get_counts()
            
            elif backendType == "IQM":
                # IQM stores timing in the metadata of the Result object
                meta = result.metadata if hasattr(result, 'metadata') else {}
                timestamps = meta.get('timestamps', {})
                created_time = timestamps.get('queued', "N/A")
                end_time = timestamps.get('finished', "N/A")
                bin_counts = result.get_counts()
            
            else: # IonQ / Generic fallback
                created_time = datetime.datetime.now().isoformat() + "Z" # Fallback
                bin_counts = result.get_counts()

            calib_data = self.get_calibration_data(backend, transpiled_circuit, backendType)
        
        timeEnd = time.time_ns()
        uTime = str(timeEnd - timeStart)[:-3]
        uTime = uTime[:-3] + "." + uTime[-3:]

        return bin_counts, data, uTime, qTime, created_time, end_time, job_id, calib_data

    def get_calibration_data(self, backend, transpiled_circuit, backendType):
        """Extracts T1, T2, and Readout Error for active qubits."""
        data = {}
        try:
            if hasattr(transpiled_circuit, "layout") and transpiled_circuit.layout:
                active_qubits = transpiled_circuit.layout.final_index_layout()
            else:
                active_qubits = range(transpiled_circuit.num_qubits)

            if backendType in ["IBM", "IQM"] and hasattr(backend, "properties"):
                props = backend.properties()
                if props:
                    for q in active_qubits:
                        data[f"q{q}"] = {
                            "T1": props.t1(q),
                            "T2": props.t2(q),
                            "readout_error": props.readout_error(q)
                        }
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