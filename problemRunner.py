import datetime, time
from typing import Optional, Tuple
import csv
from Problems.ProblemBase import ProblemBase
from qiskit_ibm_runtime import QiskitRuntimeService, Sampler, fake_provider
from iqm.qiskit_iqm.iqm_provider import IQMBackend
from iqm.qiskit_iqm.fake_backends import fake_garnet
from iqm.iqm_client import IQMClient
from qiskit.providers.backend import BackendV2

class ProblemRunner(): 
    """Class that runs QMAP Problems
    """

    def __init__(self) -> None:
        """Initializes problem runner, as well as the IQM backend urls.
        """
        self.problemArr = []
        self.IQMdict = {
            "garnet" : 'https://cocos.resonance.meetiqm.com/garnet',
            "mockGarnet" : 'https://cocos.resonance.meetiqm.com/garnet:mock', 
            "sirius" : 'https://cocos.resonance.meetiqm.com/sirius:mock'

        }

    def runProblemSet(self, backend, sampler, name, binRes) -> None:
        """
        Runs a set of problems, and inserts them into a `.csv` file. 

        Args:
            backend (BackendV2): The backend for the problem.
            sampler (Sampler): The sampler for the problem.
            name (str): The name of the problem, used in the CSV file.
            binRes (boolean): If the backend returns data in binary (True) or hexadecimal (False).

        Returns:
            None

        """

        maxQubits = backend.num_qubits

        for problem in self.problemArr:
            if problem[3] > maxQubits:
                if (problem[8]):
                    pName = problem[8]
                else:
                    pName = problem[0].name

                raise ValueError(f"Problem {pName} requires too many qubits ({problem[3]}). This backend has {maxQubits} qubits.")


        with open('dataFiles/' + str(name) + " " + str(datetime.datetime.today()) + '.csv', mode = 'w+') as csv_file:
            fieldnames = ['Problem', "Nickname",  'Results', 'Relevant Data', 'Shots', 'Time (ms)', 'quantum usage estimation (0 for n/a)']
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

            writer.writeheader()

            for problem in self.problemArr:
                for rep in range(problem[1]):
                    for qubit in range(problem[2], problem[3], problem[4]):
                        for shot in range(problem[5], problem[6], problem[7]):
                            results, rd, uTime, qTime = problem[0].run(qubit, shot, backend, sampler, binRes)
                            writer.writerow({'Problem': problem[0].name, "Nickname": problem[8] if problem[8] else "N/A", 'Results': str(results), 'Relevant Data': rd, 
                                'Shots': shot,'Time (ms)': uTime, 'quantum usage estimation (0 for n/a)': qTime})
                            time.sleep((qubit/2 + shot/100)/2)

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

    def setUpIQM(self, backendName, token) -> Tuple[BackendV2, Sampler, str, bool]:
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
            - binType (bool): True if data is binary, False if hexadecimal.
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

        binType = True
        
        return backend, sampler, backendName, binType
    
    def setUpIBM(self, backendName, token) -> Tuple[BackendV2, Sampler, str, bool]:
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
            - binType (bool): True if data is binary, False if hexadecimal.
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
        
        binType = False

        return backend, self.setUpSampler(backend), backendName, binType

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

        else:
            raise TypeError(f"Expected backend of type {BackendV2}, but got {type(backend).__name__}")
        