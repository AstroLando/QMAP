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
                # calib_data = backend_info.all_node_gate_errors() if hasattr(backend_info, 'all_node_gate_errors') else str(backend_info)
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
                job_info = getattr(job, '_job_info', {}) or getattr(job, '_metadata', {})
                created_time = job_info.get('submitted_at')
                end_time = job_info.get('completed_at')
                bin_counts = result.get_counts()

            calib_data = self.get_calibration_data(backend, transpiled_circuit)
        
        timeEnd = time.time_ns()
        uTime = str(timeEnd - timeStart)[:-3]
        uTime = uTime[:-3] + "." + uTime[-3:]

        return bin_counts, data, uTime, qTime, created_time, end_time, job_id, calib_data

    # def get_calibration_data(self, backend, active_qubits):
    #     data = {}
        
    #     # 1. Try the Target first (for Hardware/Modern Qiskit)
    #     target = getattr(backend, "target", None)
    #     if target and target.operation_names:
    #         for q in active_qubits:
    #             for gate in ['sx', 'x', 'rz', 'cx']:
    #                 if gate in target.operation_names:
    #                     props = target.get(gate).get((q,))
    #                     if props:
    #                         data[f"q{q}_{gate}_err"] = getattr(props, "error", "N/A")
    #         return data

    #     # 2. Simulator Fallback (This is where your noisy data is hiding)
    #     try:
    #         config = backend.configuration()
    #         # IonQ Simulator stores noise model info in 'noise_model' or 'basis_gates'
    #         if hasattr(config, 'noise_model'):
    #             data["noise_model_applied"] = config.noise_model
                
    #         # Check for the actual error rates stored in the backend options
    #         if hasattr(backend, 'options'):
    #             # Some versions store the dict of gate errors here
    #             data["gate_errors"] = backend.options.get("noise_model", "N/A")
                
    #     except Exception:
    #         data["info"] = "Calibration data unreachable"

    #     return data

    def get_calibration_data(self, backend, active_qubits):
        data = {}
        
        # 1. Determine the source of truth
        # If it's a simulator mimicking hardware, we need the hardware's name
        noise_model_name = backend.options.get("noise_model")
        
        # If we are on hardware, name is the backend name. 
        # If on simulator with noise, name is the noise_model_name.
        target_backend_name = noise_model_name if noise_model_name else backend.name
        
        # 2. Get the properties/target
        # For IonQ, properties() often contains the T1/T2 and gate errors
        props = None
        try:
            # If we're on a simulator, we might need to query the provider for the real properties
            if "simulator" in backend.name.lower() and noise_model_name:
                # This is a bit of a 'hack' but it's how you get the real rates
                # We assume your provider is accessible or passed in
                provider = backend.provider
                real_hw = provider.get_backend(noise_model_name)
                props = real_hw.properties()
            else:
                props = backend.properties()
        except:
            props = None

        # 3. Extract the Rates
        if props:
            for q in active_qubits:
                # Qubit Error Rates (T1/T2)
                data[f"q{q}_T1"] = props.t1(q)
                data[f"q{q}_T2"] = props.t2(q)
                
                # Gate Error Rates
                # We look for the common gates: 'sx', 'x', 'rz', 'cx', or 'ms'
                for gate in props.gates:
                    if gate.gate == 'ms' or gate.gate == 'cx': # 2-qubit
                        if q in gate.qubits and set(gate.qubits).issubset(set(active_qubits)):
                            # Format: q0q1_ms_error
                            name = "q" + "".join(map(str, gate.qubits)) + f"_{gate.gate}_err"
                            data[name] = gate.parameters[0].value
                    elif gate.gate in ['sx', 'x', 'rz']: # 1-qubit
                        if gate.qubits == [q]:
                            data[f"q{q}_{gate.gate}_err"] = gate.parameters[0].value
        else:
            # Fallback to the Target if properties are empty (Qiskit 1.x/2.x style)
            target = getattr(backend, "target", None)
            if target:
                for q in active_qubits:
                    # Iterate through operations in the target
                    for op_name, op_map in target.items():
                        if (q,) in op_map:
                            instr_props = op_map[(q,)]
                            if instr_props and hasattr(instr_props, 'error'):
                                data[f"q{q}_{op_name}_err"] = instr_props.error

        return data