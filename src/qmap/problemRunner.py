# src/qmap/ProblemRunner.py
import datetime, time, os, pandas as pd
from typing import Optional, Tuple, NamedTuple, Any
from .problems.ProblemBase import ProblemBase

# Global Qiskit import only 
from qiskit.providers.backend import BackendV2

# # Vendor Modules
# from iqm.iqm_client import IQMClient
# from iqm.qiskit_iqm import IQMBackend
# from qiskit_ibm_runtime import QiskitRuntimeService, Sampler, fake_provider
# import qnexus as qnx
# import qiskit_ionq

class ProblemConfig(NamedTuple):
    """Container to replace index-based arrays with a research-grade configuration object."""
    instance: ProblemBase
    reps: int
    min_q: int
    max_q: int
    q_step: int
    min_s: int
    max_s: int
    s_step: int
    nickname: Optional[str]

class ProblemRunner(): 
    """Class that runs QMAP Problems with atomic data persistence."""

    def __init__(self) -> None:
        self.problemArr = []

    def addProblem(self, problem: ProblemBase, **cfg) -> None:
        """
        Adds a problem using keyword arguments from config.yml.
        Defaults are applied via .get() if specific keys are missing.
        """
        if not isinstance(problem, ProblemBase):
            raise TypeError(f"Problem must be instance of ProblemBase, got {type(problem).__name__}")

        # Map dictionary keys from YAML/main.py to the NamedTuple
        config = ProblemConfig(
            instance=problem,
            reps=cfg.get('reps', 3),
            min_q=cfg.get('minQubits', 2),
            max_q=cfg.get('maxQubits', 8),
            q_step=cfg.get('qubitStep', 2),
            min_s=cfg.get('minShots', 1024),
            max_s=cfg.get('maxShots', 1024),
            s_step=cfg.get('shotStep', 0),
            nickname=cfg.get('nickname')
        )
        self.problemArr.append(config)

    def runProblemSet(self, backend, sampler, name, backendType) -> None:
        """
        Runs the batch of problems and appends results to CSV immediately.
        """
        # HPC-friendly pathing: project_root/results/
        BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        DIR = os.path.join(BASE_DIR, "results")

        if not os.path.isdir(DIR): 
            os.makedirs(DIR)

        now = datetime.datetime.now()
        date_str = now.strftime("%Y-%m-%d_%H:%M:%S")
        filename = f"{name}_{date_str}.csv"
        filepath = os.path.join(DIR, filename)

        # 1. Initialize the file with the custom metadata block
        with open(filepath, 'w') as f:
            f.write(f"Time started: {now}\n")
            f.write(f"Vendor: {backendType}\n")
            f.write(f"Backend: {name}\n\n")

        # 2. Force the Pandas column headers to write ONCE before the loop starts
        headers = [
            'problem', 'num_qubits', 'shots', 'job_id', 
            'created_time', 'end_time', 'time_RT_ms', 
            'time_QPU_ms', 'results', 'metadata', 'error_data'
        ]
        pd.DataFrame(columns=headers).to_csv(filepath, mode='a', index=False, header=True)

        # Vendor-specific qubit capacity checks
        if backendType == "Quantinuum":
            import qnexus as qnx
            qnx.login()
            project = qnx.projects.get_or_create(name="QMAP")
            qnx.context.set_active_project(project)
            device_name = backend.device_name
            max_hw_qubits = 32 if "H2" in device_name else 20
        else:
            try:
                max_hw_qubits = backend.num_qubits
            except AttributeError:
                # Fallback for IonQ or older V1 backends
                max_hw_qubits = backend.configuration().n_qubits              

        for p_cfg in self.problemArr:
            # Ensure range step is never 0
            q_step = p_cfg.q_step if p_cfg.q_step > 0 else 1

            print(f"Executing: {p_cfg.instance.name} ({p_cfg.nickname or 'no nickname'})")

            for q in range(p_cfg.min_q, p_cfg.max_q + 1, q_step):
                if q > max_hw_qubits:
                    print(f"Skipping {q}q: Exceeds capacity ({max_hw_qubits}).")
                    continue

                # Ensure shot step is never 0
                s_step = 1 if p_cfg.s_step == 0 else p_cfg.s_step

                for shot in range(p_cfg.min_s, p_cfg.max_s + 1, s_step):
                    for rep in range(p_cfg.reps):
                        print(f"  => Qubits: {q}, Shots: {shot}, Rep: {rep}")
                        try:
                            res, p_data, time_RT_ms, time_QPU_ms, cTime, eTime, jID, calib = p_cfg.instance.run(
                                q, shot, backend, sampler, backendType
                            )

                            row = {
                                'problem': p_cfg.nickname or p_cfg.instance.name,
                                'num_qubits': q,
                                'shots': shot,
                                'job_id': jID,
                                'created_time': cTime,
                                'end_time': eTime,
                                'time_RT_ms': time_RT_ms,       # Wall-clock round trip
                                'time_QPU_ms': time_QPU_ms,     # Physical hardware execution
                                'results': f'"{str(res)}"',
                                'metadata': f'"{str(p_data)}"',
                                'error_data': f'"{str(calib)}"'
                            }

                            # Atomic persistence
                            pd.DataFrame([row]).to_csv(filepath, mode='a', header=False, index=False)
                            time.sleep((q / 2 + shot / 100) / 2)

                        except Exception as e:
                            print(f"FAILED {p_cfg.instance.name} [Rep {rep}]: {e}")
                            break

        print(f"Batch complete. Data: {filepath}")

    def setUpSampler(self, backend) -> Any:
        """Helper to initialize Sampler based on backend type."""

        if isinstance(backend, BackendV2):
            from qiskit_ibm_runtime import SamplerV2
            return SamplerV2(mode=backend)
        elif type(backend).__name__ == "QuantinuumConfig":
            from qiskit_ibm_runtime import SamplerV2, fake_provider

            # TODO: Modify hardcoded fake backend for IBM here
            mock = fake_provider.FakeAlgiers()
            return SamplerV2(mode=mock)
        else:
            raise TypeError(f"Expected BackendV2, got {type(backend).__name__}")
        
    def setUpIQM(self, backendName) -> Tuple[BackendV2, Any, str, str]:
        """Sets up IQM backend."""
        from iqm.iqm_client import IQMClient
        from iqm.qiskit_iqm import IQMBackend        
        from qiskit_ibm_runtime import SamplerV2 as Sampler

        try:
            client = IQMClient("https://resonance.meetiqm.com/", quantum_computer=backendName)
            backend = IQMBackend(client, use_metrics=True)
            sampler = Sampler(mode=backend)
            return backend, sampler, backendName, "IQM"
        except Exception as e:
            raise RuntimeError(f"IQM Setup Error: {e}")

    def setUpIBM(self, backendName) -> Tuple[BackendV2, Any, str, str]:
        """Sets up IBM (handles local Aer and Cloud backends)."""
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler

        if "aer" in backendName.lower() or "simulator" in backendName.lower():
            from qiskit_aer import AerSimulator
            backend = AerSimulator()
            return backend, Sampler(), backendName, "IBM"

        try:
            service = QiskitRuntimeService(
                channel="ibm_cloud", 
                token=os.environ["IBM_TOKEN"], 
                instance=os.environ['IBM_INSTANCE']
            )
            backend = service.backend(backendName)
            return backend, Sampler(mode=backend), backendName, "IBM"
        except Exception as e:
            raise RuntimeError(f"IBM Setup Error: {e}")

    def setUpQuantinuum(self, backendName) -> Tuple[Any, Any, str, str]:
        """Sets up Quantinuum via Nexus."""
        import qnexus as qnx
        try:
            backend = qnx.QuantinuumConfig(device_name=backendName)
            sampler = self.setUpSampler(backend)
            return backend, sampler, backendName, "Quantinuum"
        except Exception as e:
            raise ValueError(f"Quantinuum Setup Error: {e}")

    def setUpIonQ(self, backendName) -> Tuple[BackendV2, Any, str, str]:
        """Sets up IonQ (Handles qpu. prefix for hardware, otherwise noisy/ideal sim)."""
        import qiskit_ionq
        from qiskit_ibm_runtime import SamplerV2

        try:
            provider = qiskit_ionq.IonQProvider(os.environ["IONQ_TOKEN"])
            
            if backendName.lower().startswith("qpu."):
                backend = provider.get_backend(backendName)
                print(f"--- REAL HARDWARE: Running on {backendName} ---")
                
            elif backendName.lower() in ["aria-1", "forte-1"]:
                backend = provider.get_backend("ionq_simulator")
                backend.set_options(noise_model=backendName.lower())
                print(f"--- NOISY SIMULATION: Modeling {backendName.lower()} ---")
                
            # 3. Default to ideal simulator
            else:
                backend = provider.get_backend("ionq_simulator")
                print("--- IDEAL SIMULATION: Running on ionq_simulator ---")
                
            return backend, SamplerV2(mode=backend), backendName, "IonQ"
        except Exception as e:
            raise RuntimeError(f"IonQ Setup Error: {e}")