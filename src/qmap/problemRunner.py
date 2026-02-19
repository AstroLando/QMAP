# src/qmap/ProblemRunner.py
import datetime, time, os, pandas as pd
from typing import Optional, Tuple, NamedTuple
from .problems.ProblemBase import ProblemBase

# Vendor Modules
from iqm.iqm_client import IQMClient
from iqm.qiskit_iqm import IQMBackend
from qiskit.providers.backend import BackendV2
from qiskit_ibm_runtime import QiskitRuntimeService, Sampler, fake_provider
import qnexus as qnx
import qiskit_ionq

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
        
        # Vendor-specific qubit capacity checks
        if backendType == "Quantinuum":
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

        date_str = datetime.datetime.today().strftime('%Y-%m-%d_%H:%M:%S')
        file_path = os.path.join(DIR, f"{name}_{date_str}.csv")

        # Headers aligned with ProblemBase return values
        headers = [
            'problem', 'num_qubits', 'shots', 'job_id', 
            'created_time', 'end_time', 'time_ms', 
            'usage_estimation', 'results', 'metadata', 'error_data'
        ]

        # Initial CSV write with metadata
        with open(file_path, mode='w') as csv_file:
            csv_file.write(f"Time started: {datetime.datetime.now()}\n")
            csv_file.write(f"Vendor: {backendType}\n")
            csv_file.write(f"Backend: {name}\n\n")
            csv_file.write(",".join(headers) + "\n")

        for p in self.problemArr:
            print(f"Executing: {p.instance.name} ({p.nickname or 'no nickname'})")

            q_step = 1 if p.q_step == 0 else p.q_step
            for qubit in range(p.min_q, p.max_q + 1, q_step):
                if qubit > max_hw_qubits:
                    print(f"Skipping {qubit}q: Exceeds capacity ({max_hw_qubits}).")
                    continue

                s_step = 1 if p.s_step == 0 else p.s_step
                for shot in range(p.min_s, p.max_s + 1, s_step):
                    for rep in range(p.reps):
                        print(f"  => Qubits: {qubit}, Shots: {shot}, Rep: {rep}")
                        try:
                            # Unpack all 8 values from ProblemBase.run
                            res, p_data, uTime, qTime, cTime, eTime, jID, calib = p.instance.run(
                                qubit, shot, backend, sampler, backendType
                            )

                            row = {
                                'problem': p.nickname or p.instance.name,
                                'num_qubits': qubit,
                                'shots': shot,
                                'job_id': jID,
                                'created_time': cTime,
                                'end_time': eTime,
                                'time_ms': uTime,
                                'usage_estimation': qTime,
                                'results': f'"{str(res)}"',
                                'metadata': f'"{str(p_data)}"',
                                'error_data': f'"{str(calib)}"'
                            }

                            # Atomic persistence
                            pd.DataFrame([row]).to_csv(file_path, mode='a', header=False, index=False)
                            time.sleep((qubit / 2 + shot / 100) / 2)

                        except Exception as e:
                            print(f"FAILED {p.instance.name} [Rep {rep}]: {e}")
                            break 

        print(f"Batch complete. Data: {file_path}")

    def setUpSampler(self, backend) -> Sampler:
        """Helper to initialize Sampler based on backend type."""
        if isinstance(backend, BackendV2):
            return Sampler(mode=backend)
        elif isinstance(backend, qnx.QuantinuumConfig):
            return Sampler(mode=fake_provider.FakeAlgiers())
        else:
            raise TypeError(f"Expected BackendV2, got {type(backend).__name__}")

    def setUpIQM(self, backendName) -> Tuple[BackendV2, Sampler, str, str]:
        """Sets up IQM backend."""
        try:
            client = IQMClient("https://resonance.meetiqm.com/", quantum_computer=backendName)
            backend = IQMBackend(client, use_metrics=True)
            sampler = Sampler(mode=backend)
            return backend, sampler, backendName, "IQM"
        except Exception as e:
            raise RuntimeError(f"IQM Setup Error: {e}")

    def setUpIBM(self, backendName) -> Tuple[BackendV2, Sampler, str, str]:
        """Sets up IBM (handles local Aer and Cloud backends)."""
        if "aer" in backendName.lower() or "simulator" in backendName.lower():
            from qiskit_aer import AerSimulator
            backend = AerSimulator()
            return backend, self.setUpSampler(backend), backendName, "IBM"

        try:
            service = QiskitRuntimeService(
                channel="ibm_cloud", 
                token=os.environ["IBM_TOKEN"], 
                instance=os.environ['IBM_INSTANCE']
            )
            backend = service.backend(backendName)
            return backend, self.setUpSampler(backend), backendName, "IBM"
        except Exception as e:
            raise RuntimeError(f"IBM Setup Error: {e}")

    def setUpQuantinuum(self, backendName) -> Tuple[qnx.QuantinuumConfig, Sampler, str, str]:
        """Sets up Quantinuum via Nexus."""
        try:
            backend = qnx.QuantinuumConfig(device_name=backendName)
            sampler = self.setUpSampler(backend)
            return backend, sampler, backendName, "Quantinuum"
        except Exception as e:
            raise ValueError(f"Quantinuum Setup Error: {e}")

    def setUpIonQ(self, backendName) -> Tuple[BackendV2, Sampler, str, str]:
        """Sets up IonQ (Handles qpu. prefix for hardware, otherwise noisy/ideal sim)."""
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
                
            return backend, Sampler(mode=backend), backendName, "IonQ"
        except Exception as e:
            raise RuntimeError(f"IonQ Setup Error: {e}")