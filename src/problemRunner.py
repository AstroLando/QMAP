import datetime, time
from typing import Optional, Tuple
from Problems.ProblemBase import ProblemBase
from qiskit_ibm_runtime import QiskitRuntimeService, Sampler, fake_provider
from iqm.qiskit_iqm.iqm_provider import IQMBackend
from iqm.iqm_client import IQMClient
from qiskit.providers.backend import BackendV2
from pytket.extensions.quantinuum import QuantinuumBackend
import os, pandas as pd

from pytket.extensions.quantinuum import QuantinuumAPI;
from pytket.extensions.quantinuum.backends.credential_storage import MemoryCredentialStorage

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

        backendTypeList = ["IQM", "IBM", "Quantinuum"]

        if backendType not in backendTypeList:
            raise ValueError("BackendType not usable.")

        if backendType == "Quantinuum":
            maxQubits = backend.backend_info.n_nodes
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
            csv_file.write(f"Backend: {name}\n")
            csv_file.write(f"Problems: {str(pNames)}\n")
            csv_file.write("\n")
            csv_file.write("Problem, Nickname, Results, Shots, Time (ms), Quantum Usage Estimation, Metadata\n")

        # Prepare a list to hold all rows
        rows = []

        # Check if the file already exists to decide if we need to write headers
        file_exists = os.path.exists(file_path)

        # Run experiments and append data to DataFrame
        for problem in self.problemArr:
            print(f"Problem: {problem[0].name}")
            for qubit in range(problem[2], problem[3] + 1, problem[4]):
                print(f"{' ':2}=> Qubits: {qubit}")
                for shot in range(problem[5], problem[6] + 1, problem[7]):
                    for rep in range(problem[1]):
                        print(f"{' ':8}Shots: {shot}, Rep: {rep}")
                        try:
                            # Run the experiment and get the results
                            results, rd, uTime, qTime = problem[0].run(qubit, shot, backend, sampler, backendType)

                            # Collect the data into the rows list
                            rows.append({
                                'Problem': problem[0].name,
                                'Nickname': problem[8] if problem[8] else "N/A",
                                'Results': str(results),
                                'Shots': shot,
                                'Time (ms)': uTime,
                                'Quantum Usage Estimation': qTime,
                                'Metaata': rd,
                            })

                            # Sleep for a small time to simulate processing delay
                            time.sleep((qubit / 2 + shot / 100) / 2)

                        except Exception as e:
                            # Log the error and continue to the next experiment
                            print(f"Error occurred while running experiment for problem {problem[0].name}: {e}")

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
               minShots: int = 100,
               maxShots: int = 1000,
               shotStep: int = 100,
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
        
        elif(isinstance(backend, QuantinuumBackend)):
            #unused, so dummy info used here
            return Sampler(mode = fake_provider.FakeAlgiers())

        else:
            raise TypeError(f"Expected backend of type {BackendV2}, but got {type(backend).__name__}")

    def setUpIQM(self, backendName, token) -> Tuple[BackendV2, Sampler, str, str]:
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
        self.IQMdict = {
            "garnet" : 'https://cocos.resonance.meetiqm.com/garnet',
            "garnet_mock" : 'https://cocos.resonance.meetiqm.com/garnet:mock', 
            "sirius" : 'https://cocos.resonance.meetiqm.com/sirius',
            "sirius_mock" : 'https://cocos.resonance.meetiqm.com/sirius:mock',
            "emerald": "https://cocos.resonance.meetiqm.com/emerald",
            "emerald_mock": "https://cocos.resonance.meetiqm.com/emerald:mock"
        }

        try:
            backendURL = self.IQMdict[backendName]
        except KeyError:
            raise ValueError(f"Backend '{backendName}' does not exist in available QMAP backends dictionary")

        try:
            # backend = provider.get_backend()
            os.environ.pop('IQM_TOKEN', None)
            backend = IQMBackend(IQMClient(backendURL, token=token))
            print(f"{' ':4}Successfully retrieved backend: {backendName}")
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve backend: {str(e)}")

        try:
            sampler = Sampler(mode=backend)
            print(f"{' ':4}Successfully retrieved sampler!")
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve sampler: {str(e)}")
            
        return backend, sampler, backendName, "IQM"
    
    def setUpIBM(self, backendName, token, instance) -> Tuple[BackendV2, Sampler, str, str]:
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

        if token:
            try:
                IBMservice = QiskitRuntimeService(token = token, channel= 'ibm_quantum_platform', instance = instance)
            except Exception as e:
                raise RuntimeError(f"Failed to initialize IBM backends: {e}")
        else:
            raise ValueError("No token provided")
        
        self.IBMDict = {
            "leastBusy" : IBMservice.least_busy(operational=True),
            "ibm_brisbane" : IBMservice.backend("ibm_brisbane"),
            "brisbane_fake" : fake_provider.FakeBrisbane(),
            "ibm_fez" : IBMservice.backend("ibm_fez"),
            "ibm_kingston" : IBMservice.backend("ibm_kingston"),
            "ibm_aachen" : IBMservice.backend("ibm_aachen")
        }
            
        try:
            backend = self.IBMDict[backendName]
        except KeyError:
            raise ValueError(f"Backend '{backendName}' does not exist in available backends")

        return backend, self.setUpSampler(backend), backendName, "IBM"
    
    def setUpQuantinuum(self, backendName) -> Tuple[QuantinuumBackend, Sampler, str, str]:
        """
        Sets up an Quantinuum backend

        Args:
            backendName (str): The name for the backend (in the dictionary).
            username (str): Your Quantinuum username.
            username (str): Your Quantinuum password.

        Returns:
            Tuple  [BackendV2, Sampler, str, bool]: A tuple containing:
            - backend (BackendV2): The chosen backend.
            - sampler (Sampler): The sampler associated with the backend.
            - backendName (str): The name of the backend.
            - backendType (string): Which company backend you are using.
        """

        self.QuantinuumDict = {
            "H1-1E" : 'H1-1E', 
            "H1-1SC" : 'H1-1SC',
            "H1-1": "H1-1",
            "H2-1E" : 'H2-1E',
            "H2-2E" : 'H2-2E',
            "H2-1SC": "H2-1SC",
            "H2-1": "H2-1",
            "H2-2": "H2-2",
        }

        try:
            backend = self.QuantinuumDict[backendName]
        except KeyError:
            raise ValueError(f"Backend '{backendName}' does not exist in available backends")
        
        backend = QuantinuumBackend(backend)
            
        sampler = self.setUpSampler(backend)
        
        return backend, sampler, backendName, "Quantinuum"