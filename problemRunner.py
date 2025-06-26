import datetime, time
from typing import Optional, Tuple
import csv
from Problems.ProblemBase import ProblemBase
from qiskit_ibm_runtime import QiskitRuntimeService, Sampler, fake_provider
from iqm.qiskit_iqm.iqm_provider import IQMBackend
from iqm.qiskit_iqm.fake_backends import fake_garnet
from iqm.iqm_client import IQMClient
from qiskit.providers.backend import BackendV2
from pytket.extensions.quantinuum import QuantinuumBackend

from pytket.extensions.quantinuum import QuantinuumAPI;
from pytket.extensions.quantinuum.backends.credential_storage import MemoryCredentialStorage

class ProblemRunner(): 
    """Class that runs QMAP Problems
    """

    def __init__(self) -> None:
        """Initializes problem runner, as well as the IQM backend urls.
        """
        self.problemArr = []
        self.IQMdict = {
            "garnet" : 'https://cocos.resonance.meetiqm.com/garnet',
            "sirius" : 'https://cocos.resonance.meetiqm.com/sirius',
            "mockGarnet" : 'https://cocos.resonance.meetiqm.com/garnet:mock', 
            "mockSirius" : 'https://cocos.resonance.meetiqm.com/sirius:mock',
            "emerald": "https://cocos.resonance.meetiqm.com/emerald",
            "mockEmerald": "https://cocos.resonance.meetiqm.com/emerald:mock"

        }

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


        with open('dataFiles/' + str(name) + " " + str(datetime.datetime.today() ) + '.csv', mode = 'w+') as csv_file:
            writer = csv.writer(csv_file)
            s = datetime.datetime.today()

            writer.writerow(["Time started: " + str(s)])
            writer.writerow(["Backend: " + name])
            writer.writerow(["Problems: " + str(pNames)])
            writer.writerow([])

            fieldnames = ['Problem', "Nickname",  'Results', 'Relevant Data', 'Shots', 'Time (ms)', 'quantum usage estimation']
            dictWriter = csv.DictWriter(csv_file, fieldnames=fieldnames)

            dictWriter.writeheader()

            for problem in self.problemArr:
                for qubit in range(problem[2], problem[3] + 1, problem[4]):
                    for shot in range(problem[5], problem[6] + 1, problem[7]):
                        for rep in range(problem[1]):
                            results, rd, uTime, qTime = problem[0].run(qubit, shot, backend, sampler, backendType)
                            dictWriter.writerow({'Problem': problem[0].name, "Nickname": problem[8] if problem[8] else "N/A", 'Results': str(results), 'Relevant Data': rd, 
                                'Shots': shot,'Time (ms)': uTime, 'quantum usage estimation': qTime})
                            time.sleep((qubit/2 + shot/100)/2)

            e = datetime.datetime.today()
            writer.writerow([])
            writer.writerow(["Time ended: " + str(e)])
            td = str(e - s).split(":")
            tStr = "Time difference: " + td[0] + " hours; " + td[1] + " minutes; " + td[2] + " seconds"
            writer.writerow([tStr])

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

        if (backendName == "fakeGarnet"):
            backend = fake_garnet.IQMFakeGarnet()
        else:
            try:
                backendURL = self.IQMdict[backendName]
            except KeyError:
                raise ValueError(f"Backend '{backendName}' does not exist in available backends")
            
            backend = IQMBackend(IQMClient(backendURL, token = token))
            
        sampler = Sampler(mode = backend)
        
        return backend, sampler, backendName, "IQM"
    
    def setUpIBM(self, backendName, token) -> Tuple[BackendV2, Sampler, str, str]:
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
                IBMservice = QiskitRuntimeService(token = token, channel= 'ibm_quantum')
            except Exception as e:
                raise RuntimeError(f"Failed to initialize IBM backends: {e}")
        else:
            raise ValueError("No token provided")
        
        if not hasattr(self, 'IBMDict'):
            self.IBMDict = {
                "leastBusy" : IBMservice.least_busy(operational=True),
                "fakeBrisbane" : fake_provider.FakeBrisbane(),
                "brisbane" : IBMservice.backend("ibm_brisbane"),
                "fez" : IBMservice.backend("ibm_fez")
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

        try:
            backend = self.QuantinuumDict[backendName]
        except KeyError:
            raise ValueError(f"Backend '{backendName}' does not exist in available backends")
        
        backend = QuantinuumBackend(backend)
            
        sampler = self.setUpSampler(backend)
        
        return backend, sampler, backendName, "Quantinuum"

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