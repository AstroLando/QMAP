# src/qmap/problems/ProblemBase.py
import time, os, datetime
from typing import Tuple
from abc import ABC, abstractmethod

# import qnexus as qnx
# from pytket.extensions.qiskit import qiskit_to_tk

# Global Qiskit imports (safe for all environments)
from qiskit import transpile
from qiskit import QuantumCircuit
from qiskit.transpiler import CouplingMap
from qiskit.providers.backend import BackendV2

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
            import qnexus as qnx
            from pytket.extensions.qiskit import qiskit_to_tk
            
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

            qTime, created_time, end_time = self._extract_qpu_telemetry("Quantinuum", job_ref=result_ref)

            try:
                backend_info = result_ref.download_backend_info()
                # calib_data = backend_info.all_node_gate_errors() if hasattr(backend_info, 'all_node_gate_errors') else str(backend_info)
                calib_data = backend_info.to_dict() if hasattr(backend_info, 'to_dict') else str(backend_info)
            except Exception as e:
                calib_data = f"Quantinuum fetch error: {str(e)}"

            # QNexus stores system metrics on the job record
            job_record = qnx.jobs.get(result_ref)
            try:
                # Quantinuum exposes total hardware execution time here
                duration_seconds = job_record.metrics.machine_execution_time
                if duration_seconds:
                    time_QPU_ms = duration_seconds * 1000.0
                    qTime = f"{time_QPU_ms:.3f}"
                else:
                    qTime = "N/A"
            except AttributeError:
                qTime = "N/A"

        # Extraction logic for Server-Side Timestamps
        elif backendType == "IBM":
            transpiled_circuit = transpile(circ, backend=backend, optimization_level=3)
            job = sampler.run([transpiled_circuit], shots=shots)
            result = job.result()
            job_id = job.job_id()
            bin_counts = result[0].data.c.get_counts()
            
            qTime, created_time, end_time = self._extract_qpu_telemetry("IBM", job=job, result=result)

            # # IBM tracks physical execution time in quantum seconds
            # metrics = job.metrics()
            # ts = metrics.get('timestamps', {})
            # created_time = ts.get('created', "N/A")
            # end_time = ts.get('finished', "N/A")
            # qTime = job.usage_estimation.get('quantum_seconds', "N/A") if hasattr(job, 'usage_estimation') else "N/A"
            
        elif backendType == "IQM":
            # Drop optimization to 1 to bypass the IQMNaiveMovePass hashing bug in Qiskit 2.x
            transpiled_circuit = transpile(circ, backend=backend, optimization_level=1)
            job = backend.run(transpiled_circuit, shots=shots)
            result = job.result()
            
            bin_counts = result.get_counts()
            job_id = job.job_id()

            qTime, created_time, end_time = self._extract_qpu_telemetry("IQM", backend=backend, job_id=job_id)

            # # Bypass Qiskit and ask the native IQM client for the raw job payload
            # try:
            #     raw_iqm_job = backend.client.get_job(job_id)
                
            #     timeline = []
            #     if hasattr(raw_iqm_job, 'data') and hasattr(raw_iqm_job.data, 'timeline'):
            #         timeline = raw_iqm_job.data.timeline
                
            #     raw_created = None
            #     raw_end = None
                
            #     # Loop through the event array
            #     for event in timeline:
            #         status = getattr(event, 'status', None) or (event.get('status') if isinstance(event, dict) else None)
            #         ts = getattr(event, 'timestamp', None) or (event.get('timestamp') if isinstance(event, dict) else None)
                    
            #         if status == 'execution_started':
            #             raw_created = ts
            #             created_time = str(ts)
            #         elif status == 'execution_ended':
            #             raw_end = ts
            #             end_time = str(ts)

            #     # Calculate QPU time using native datetime math
            #     if raw_created and raw_end:
            #         delta = raw_end - raw_created
            #         time_QPU_ms = delta.total_seconds() * 1000
            #         qTime = f"{time_QPU_ms:.3f}"
            #     else:
            #         qTime = "N/A"
                    
            # except Exception as e:
            #     print(f"Failed to fetch raw IQM metadata: {e}")
            #     qTime = "N/A"
        
        elif backendType == "IonQ": # IonQ / Generic fallback
            transpiled_circuit = transpile(circ, backend=backend, optimization_level=1)
            job = backend.run(transpiled_circuit, shots=shots)
            job_id = job.job_id()
            result = job.result()
            bin_counts = result.get_counts()

            qTime, created_time, end_time = self._extract_qpu_telemetry("IonQ", result=result)
            
            # job_info = getattr(job, '_job_info', {}) or getattr(job, '_metadata', {})
            # created_time = job_info.get('submitted_at')
            # end_time = job_info.get('completed_at')

            # # # IonQ: time_taken
            # if hasattr(result, 'time_taken') and result.time_taken:
            #     qTime = f"{result.time_taken * 1000.0:.3f}"
            # else:
            #     timing = getattr(result, 'metadata', {}).get('timing', {})
            #     if 'execution' in timing:
            #         qTime = f"{timing['execution'] * 1000.0:.3f}"

        else:  # Fallback for simulators
            transpiled_circuit = transpile(circ, backend=backend, optimization_level=1)
            job = backend.run(transpiled_circuit, shots=shots)
            result = job.result()
            job_id = job.job_id()
            bin_counts = result.get_counts()
            qTime, created_time, end_time = "N/A", "N/A", "N/A"    


        calib_data = self.get_calibration_data(backend, range(qubits))

        # Explicitly map the variables to what they actually represent
        time_RT_ms = self._calculate_rt_time_ms(timeStart)
        time_QPU_ms = qTime

        return bin_counts, data, time_RT_ms, time_QPU_ms, created_time, end_time, job_id, calib_data
    
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

                # Explicitly pull the readout error (critical for IBM/superconducting)
                try:
                    data[f"q{q}_readout_err"] = props.readout_error(q)
                except Exception:
                    pass
                
                # Gate Error Rates
                # We look for the common gates: 'sx', 'x', 'rz', 'cx', or 'ms'
                for gate in props.gates:
                    if gate.gate in ['cx', 'ms', 'ecr', 'cz']: 
                        if q in gate.qubits and set(gate.qubits).issubset(set(active_qubits)):
                            name = "q" + "".join(map(str, gate.qubits)) + f"_{gate.gate}_err"
                            data[name] = gate.parameters[0].value
                            
                    elif gate.gate in ['sx', 'x', 'rz']: 
                        if gate.qubits == [q]:
                            data[f"q{q}_{gate.gate}_err"] = gate.parameters[0].value
        else:
            # Fallback to the Target if properties are empty (Qiskit 1.x/2.x style)
            target = getattr(backend, "target", None)
            if target:
                for q in active_qubits:
                    for op_name, op_map in target.items(): # Iterate through operations in the target
                        if (q,) in op_map:
                            instr_props = op_map[(q,)]
                            if instr_props and hasattr(instr_props, 'error'):
                                data[f"q{q}_{op_name}_err"] = instr_props.error

        return data
    
    def _calculate_rt_time_ms(self, start_time_ns) -> str:
        """Calculates total wall-clock round trip time in milliseconds."""
        local_rt_ns = time.time_ns() - start_time_ns
        return f"{local_rt_ns / 1_000_000.0:.3f}"

    def _extract_qpu_telemetry(self, backendType, job=None, result=None, backend=None, job_id=None, job_ref=None) -> tuple[str, str, str]:
        """Isolates vendor-specific payload parsing to extract physical hardware execution time."""
        created_time = "N/A"
        end_time = "N/A"
        qTime = "N/A"

        try:
            # if backendType == "IBM" and job:
            #     q_seconds = job.metrics().get("usage", {}).get("quantum_seconds")
            #     if q_seconds is not None:
            #         qTime = f"{q_seconds * 1000.0:.3f}"

            if backendType == "IBM" and job:
                # 1. Fetch metrics dictionary (standard for Runtime V2)
                metrics = job.metrics()
                ts = metrics.get('timestamps', {})
                
                # Extract timestamps safely
                created_time = ts.get('created', "N/A")
                end_time = ts.get('finished', "N/A")

                # 2. Extract QPU time (quantum_seconds)
                # Try the newer metrics path first, then fallback to usage_estimation
                q_seconds = metrics.get('usage', {}).get('quantum_seconds')
                
                if q_seconds is None and hasattr(job, 'usage_estimation'):
                    q_seconds = job.usage_estimation.get('quantum_seconds')

                # 3. Only apply formatting if we actually have a number
                if q_seconds is not None:
                    try:
                        qTime = f"{float(q_seconds) * 1000.0:.3f}" # Convert to ms
                    except (ValueError, TypeError):
                        qTime = "N/A"
                else:
                    qTime = "N/A"

            elif backendType == "IonQ" and result:
                if hasattr(result, 'time_taken') and result.time_taken:
                    qTime = f"{result.time_taken * 1000.0:.3f}"
                else:
                    timing = getattr(result, 'metadata', {}).get('timing', {})
                    if 'execution' in timing:
                        qTime = f"{timing['execution'] * 1000.0:.3f}"

            elif backendType == "IQM" and backend and job_id:
                raw_iqm_job = backend.client.get_job(job_id)
                timeline = getattr(getattr(raw_iqm_job, 'data', None), 'timeline', [])
                
                raw_created, raw_end = None, None
                for event in timeline:
                    status = getattr(event, 'status', None) or (event.get('status') if isinstance(event, dict) else None)
                    ts = getattr(event, 'timestamp', None) or (event.get('timestamp') if isinstance(event, dict) else None)
                    
                    if status == 'execution_started':
                        raw_created = ts
                        created_time = str(ts)
                    elif status == 'execution_ended':
                        raw_end = ts
                        end_time = str(ts)

                if raw_created and raw_end:
                    delta = raw_end - raw_created
                    qTime = f"{delta.total_seconds() * 1000.0:.3f}"

            elif backendType == "Quantinuum" and job_ref:
                import qnexus as qnx
                job_record = qnx.jobs.get(job_ref)
                duration_seconds = job_record.metrics.machine_execution_time
                if duration_seconds:
                    qTime = f"{duration_seconds * 1000.0:.3f}"
                    
        except Exception as e:
            print(f"Telemetry extraction failed for {backendType}: {e}")

        return qTime, created_time, end_time