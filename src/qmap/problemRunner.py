# src/qmap/problemRunner.py
import datetime, time, os, pandas as pd
from typing import Optional, Tuple
from .problems.ProblemBase import ProblemBase

# IQM Modules
from iqm.iqm_client import IQMClient
from iqm.qiskit_iqm import IQMBackend

# IBM Modules
from qiskit.providers.backend import BackendV2
from qiskit_ibm_runtime import QiskitRuntimeService, Sampler, fake_provider

# Quantinuum Modules
import qnexus as qnx

# IonQ Modules
import qiskit_ionq

class ProblemRunner(): 
    """Class that runs QMAP Problems
    """

    def __init__(self) -> None:
        """Initializes problem runner.
        """
        self.problemArr = []

    def runProblemSet(self, backend, sampler, name, backendType) -> None:
        """
        Runs a set of problems, and inserts them into a `.csv` file. 

        Args:
            backend (BackendV2): The backend for the problem.
            sampler (Sampler): The sampler for the problem.
            name (str): The name of the backend.
            backendType (string): Which company backend you are using.

        Returns:
            None

        """
        backendTypeList = ["IQM", "IBM", "Quantinuum", "IonQ"]

        if backendType not in backendTypeList:
            raise ValueError("BackendType not usable.")

        if backendType == "Quantinuum":
            qnx.login() # Authenticate with Nexus

            # Get or create project to store jobs 
            project = qnx.projects.get_or_create(name="QMAP")

            # Set project as active for current session
            qnx.context.set_active_project(project)
            
            # Map standard devices to qubits
            device_name = backend.device_name
            if "H2" in device_name:
                maxQubits = 32
            elif "H1" in device_name:
                maxQubits = 20
            else:
                # Fallback number of qubits 
                maxQubits = 20
                print(f"Warning: Qubit count for {device_name} unknown. Defaulting to 20 qubits.")
        else:
            maxQubits = backend.num_qubits                

        pNames = []

        for problem in self.problemArr:
            pName = ""
            if (problem[8]):
                pName = problem[8]
            else:
                pName = problem[0].name

            if problem[3] > maxQubits:
                raise ValueError(f"Problem {pName} requires too many qubits ({problem[3]}). This backend has {maxQubits} qubits.")
            
            pNames.append(pName)

        # Prepare the file path - make sure path exists 
        DIR = "results"
        if not os.path.isdir(DIR):
            os.makedirs(DIR)
        file_path = f"{DIR}/{name}_{datetime.datetime.today()}.csv"

        # Write initial info and column headers once
        with open(file_path, mode='w+') as csv_file:
            s = datetime.datetime.today()

            # Write general experiment details
            csv_file.write(f"Time started: {str(s)}\n")
            csv_file.write(f"Vendor: {backendType}\n")
            csv_file.write(f"Backend: {name}\n")
            csv_file.write(f"Problems: {str(pNames)}\n")
            csv_file.write("\n")
            csv_file.write("problem,num_qubits,shots,end_time,time_ms,usage_estimation,results,metadata,error_data\n")

        # Prepare a list to hold all rows
        rows = []

        # Check if the file already exists to decide if we need to write headers
        file_exists = os.path.exists(file_path)

        # Run experiments and append data to DataFrame
        for problem in self.problemArr:
            print(f"Problem: {problem[0].name}")

            end_qubit_range = 1 if problem[4] == 0 else problem[4]
            for qubit in range(problem[2], problem[3] + 1, end_qubit_range):
                print(f"{' ':2}=> Qubits: {qubit}")

                end_shots_range = 1 if problem[7] == 0 else problem[7]
                for shot in range(problem[5], problem[6] + 1, end_shots_range):
                    for rep in range(problem[1]):
                        print(f"{' ':8}Shots: {shot}, Rep: {rep}")
                        try:
                            # Run the experiment and get the results
                            results, rd, uTime, qTime, end_time, calib_data = problem[0].run(qubit, shot, backend, sampler, backendType)

                            # Collect the data into the rows list
                            rows.append({
                                'problem': problem[0].name,
                                'num_qubits': qubit,
                                'shots': shot,
                                'end_time': end_time,
                                'time_ms': uTime,
                                'usage_estimation': qTime,
                                'results': str(results),
                                'metadata': str(rd),
                                'error_data': str(calib_data),
                            })

                            # Sleep for a small time to simulate processing delay
                            time.sleep((qubit / 2 + shot / 100) / 2)

                        except Exception as e:
                            # Log the error and continue to the next experiment
                            print(f"Error occurred while running experiment for problem {problem[0].name}: {e}")
                            print(f"====> Stopping experiments...")
                            break

                        # Periodically write the rows to CSV to avoid data loss
                        if rep % 5 == 0:  
                            if rows:
                                temp_df = pd.DataFrame(rows)

                                # If the file exists, append without headers, else write with headers
                                temp_df.to_csv(file_path, mode='a', header=not file_exists, index=False)
                                rows.clear()  # Clear the list after writing to avoid duplicates
                                file_exists = True  # After the first write, ensure header is not written again


            print("--------------")

        print(f"Saving results in {file_path}")

        # After all experiments are done, record the time the experiment ended
        e = datetime.datetime.today()
        with open(file_path, mode='a') as csv_file:
            csv_file.write("\n")
            csv_file.write(f"Time ended: {str(e)}\n")

            # Calculate and write the total time taken
            td = str(e - s).split(":")
            tStr = f"Time difference: {td[0]} hours; {td[1]} minutes; {td[2]} seconds"
            csv_file.write(f"{tStr}\n")

        # Finally, write any remaining rows to the CSV (if not done earlier)
        if rows:
            temp_df = pd.DataFrame(rows)
            temp_df.to_csv(file_path, mode='a', header=False, index=False)
        
        return

    def addProblem(self,
               problem: ProblemBase,
               reps: int = 3,
               minQubits: int = 2,
               maxQubits: int = 8,
               qubitStep: int = 2,
               minShots: int = 1024,
               maxShots: int = 1024,
               shotStep: int = 0,
               nickname: Optional[str] = None) -> None:
        """
        Adds a problem with its execution parameters.

        Args:
            problem (ProblemBase): The problem instance.
            reps (int): Number of repetitions for the problem.
            minQubits (int): Minimum number of qubits to test.
            maxQubits (int): Maximum number of qubits to test.
            qubitStep (int): Step size for qubit count.
            minShots (int): Minimum shots to test.
            maxShots (int): Maximum shots to test.
            shotStep (int): Step size for shots.
            nickname (str, optional): Nickname for the problem, useful for differentiating
                parameter sets for the same problem.

        Returns:
            None
        """


        if not isinstance(problem, ProblemBase):
            raise TypeError(f"Problem must be instance of a subclass of ProblemBase, got {type(problem).__name__} instead")
        
        int_args = {
            "reps": reps,
            "minQubits": minQubits,
            "maxQubits": maxQubits,
            "minShots": minShots,
            "maxShots": maxShots,
            "qubitStep": qubitStep,
            "shotStep": shotStep,
        }

        for name, value in int_args.items():
            if not isinstance(value, int):
                raise TypeError(f"'{name}' must be an int, got {type(value).__name__} instead.")
        
        for name, value in int_args.items():
            if name != "shotStep" and name != "qubitStep":
                if value <= 0:
                    raise ValueError(f"'{name}' must be greater than or equal to 1, got {value} instead.")
            

        if minQubits > maxQubits:
            raise ValueError("maxQubits must be greater than or equal to minQubits")
        
        if minShots > maxShots:
            raise ValueError("maxShots must be greater than or equal to minShots")

        self.problemArr.append([problem, reps, minQubits, maxQubits, qubitStep, minShots, maxShots, shotStep, nickname])
        return
    
    def setUpSampler(self, backend)  -> Sampler:
        """
        Sets up a sampler for a backend.

        Args:
            backend (BackendV2): The backend you want to create a sampler for.

        Returns:
            sampler (Sampler): The sampler for the input backend.
        """
        if (isinstance(backend, BackendV2)):
            return Sampler(mode = backend)
        
        elif(isinstance(backend, qnx.QuantinuumConfig)):
            #unused, so dummy info used here
            return Sampler(mode = fake_provider.FakeAlgiers())

        else:
            raise TypeError(f"Expected backend of type {BackendV2}, but got {type(backend).__name__}")

    def setUpIQM(self, backendName) -> Tuple[BackendV2, Sampler, str, str]:
        """
        Sets up an IQM backend

        Args:
            backendName (str): The name for the backend (in the dictionary).
            token (str): Your IQM token.

        Returns:
            Tuple  [BackendV2, Sampler, str, bool]: A tuple containing:
            - backend (BackendV2): The chosen backend.
            - sampler (Sampler): The sampler associated with the backend.
            - backendName (str): The name of the backend.
            - backendType (string): Which company backend you are using.
        """
        # Set up IQM Backend
        try:
            client = IQMClient("https://resonance.meetiqm.com/", quantum_computer=backendName)
            backend = IQMBackend(client, use_metrics=True)

            print(f"{' ':4}Successfully retrieved backend: {backendName}\n")
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve backend: {str(e)}\n")

        # Set up IQM Sampler
        try:
            sampler = Sampler(mode=backend)
            print(f"{' ':4}Successfully retrieved sampler!\n")
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve sampler: {str(e)}\n")
            
        return backend, sampler, backendName, "IQM"
    
    def setUpIBM(self, backendName) -> Tuple[BackendV2, Sampler, str, str]:
        """
        Sets up an IBM backend

        Args:
            backendName (str): The name for the backend (in the dictionary).
            token (str): Your IBM token.

        Returns:
            Tuple  [BackendV2, Sampler, str, bool]: A tuple containing:
            - backend (BackendV2): The chosen backend.
            - sampler (Sampler): The sampler associated with the backend.
            - backendName (str): The name of the backend.
            - backendType (string): Which company backend you are using.
        """

        if "aer" in backendName:
            # Simulate machine with aer_simulator via Noise Models
            try:
                from qiskit_aer import AerSimulator
                backend = AerSimulator()
                print(f"{' ':4}Successfully retrieved local backend: {backendName}\n")
                sampler = self.setUpSampler(backend)
                return backend, sampler, backendName, "IBM"
            except ImportError:
                raise RuntimeError("You requested 'aer_simulator', but 'qiskit-aer' is not installed.")

        try:
            service = QiskitRuntimeService(channel="ibm_cloud", token=os.environ["IBM_TOKEN"], instance=os.environ['IBM_INSTANCE'])
            print(f"{' ':4}Successfully retrieved project instance\n")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize IBM Qiskit Runtime Service: {e}\n")
        
        try:
            backend = service.backend(backendName)
            print(f"{' ':4}Successfully retrieved backend: {backendName}\n")
        except Exception as e:
            raise RuntimeError(f"Backend does not exist. Please see IBM Quantum Cloud for list of active backends.\n")
            
        return backend, self.setUpSampler(backend), backendName, "IBM"
    
    def setUpQuantinuum(self, backendName) -> Tuple[qnx.QuantinuumConfig, Sampler, str, str]:
        """
        Sets up an Quantinuum backend

        Args:
            backendName (str): The name for the backend (in the dictionary).
            username (str): Your Quantinuum username.
            username (str): Your Quantinuum password.

        Returns:
            Tuple  [qnx.QuantinuumConfig, Sampler, str, bool]: A tuple containing:
            - backend (qnx.QuantinuumConfig): The chosen backend.
            - sampler (Sampler): The sampler associated with the backend.
            - backendName (str): The name of the backend.
            - backendType (str): Which company backend you are using.
        """

        try:
            backend = qnx.QuantinuumConfig(device_name=backendName)
            print(f"{' ':4}Successfully retrieved backend: {backendName}\n")
        except Exception as e:
            raise ValueError(f"Backend '{backendName}' does not exist in available Quantinuum backends.")
        
        # Set up sampler on Quantinuum backend
        sampler = self.setUpSampler(backend)
        
        return backend, sampler, backendName, "Quantinuum"
    
    def setUpIonQ(self, backendName) -> Tuple[BackendV2, Sampler, str, str]:
        """
        Sets up an Quantinuum backend

        Args:
            backendName (str): The name for the backend (in the dictionary).

        Returns:
            Tuple[BackendV2, Sampler, str, bool]: A tuple containing:
            - backend (BackendV2): The chosen backend.
            - sampler (Sampler): The sampler associated with the backend.
            - backendName (str): The name of the backend.
            - backendType (string): Which company backend you are using.
        """

        # Set up IonQ client
        try:
            provider = qiskit_ionq.IonQProvider(os.environ["IONQ_TOKEN"])
            print(f"{' ':4}Successfully retrieved provider: {backendName}\n")
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve provider: {str(e)}\n")
            
        # Set up IonQ backend
        try:
            backend = provider.get_backend("simulator")
            if backendName == "aria-1" or backendName == "forte-1":
                backend.set_options(noise_model=backendName)
            print(f"{' ':4}Successfully retrieved backend: {backendName}\n")
        except Exception as e:
            raise RuntimeError(f"Failed to access backend: {str(e)}\n")

        # Set up IonQ Sampler
        try:
            sampler = Sampler(mode=backend)
            print(f"{' ':4}Successfully retrieved sampler!\n")
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve sampler: {str(e)}\n")
            
            
        return backend, sampler, backendName, "IonQ"