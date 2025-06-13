import datetime, time
import csv
import Problems
from qiskit_ibm_runtime import QiskitRuntimeService, Sampler, fake_provider
from iqm.qiskit_iqm.iqm_provider import IQMBackend
from iqm.qiskit_iqm.fake_backends import fake_garnet
from iqm.iqm_client import IQMClient
from qiskit.providers.backend import Backend

class ProblemRunner():
    def __init__(self):
        self.problemArr = []
        self.IQMdict = {
            "garnet" : 'https://cocos.resonance.meetiqm.com/garnet',
            "mockGarnet" : 'https://cocos.resonance.meetiqm.com/garnet:mock', 
            "sirius" : 'https://cocos.resonance.meetiqm.com/sirius:mock'

        }

    def runProblemSet(self, backend, sampler, name, hexRes):
        maxQubits = backend.num_qubits

        for i in self.problemArr:
            if i[3] > maxQubits:
                if (i[8]):
                    pName = i[8]
                else:
                    pName = i[0].name

                raise ValueError(f"Problem {pName} requires too many qubits ({i[3]}). This backend has {maxQubits} qubits.")


        with open('dataFiles/' + str(name) + " " + str(datetime.datetime.today()) + '.csv', mode = 'w+') as csv_file:
            fieldnames = ['Problem', "Nickname",  'Results', 'Relevant Data', 'Shots', 'Time (ms)', 'quantum usage estimation (0 for n/a)']
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

            writer.writeheader()

            for _ in self.problemArr:
                for rep in range(_[1]):
                    for qubit in range(_[2], _[3], _[4]):
                        for shot in range(_[5], _[6], _[7]):
                            results, rd, uTime, qTime = _[0].run(qubit, shot, backend, sampler, hexRes)
                            writer.writerow({'Problem': _[0].name, "Nickname": _[8] if _[8] else "N/A", 'Results': str(results), 'Relevant Data': rd, 
                                'Shots': shot,'Time (ms)': uTime, 'quantum usage estimation (0 for n/a)': qTime})
                            time.sleep((qubit/2 + shot/100)/2)

    def addProblem(self, problem, reps = 3, minQubits = 2, maxQubits = 8, qubitStep = 2, minShots = 100, maxShots = 1000, shotStep = 100, nickname = None):
        if not isinstance(problem, Problems.ProblemBase.ProblemBase):
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

    def setUpIQM(self, backendName, token):
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
    
    def setUpIBM(self, backendName, token):

        if token:
            try:
                IBMservice = QiskitRuntimeService(token = token, channel= 'ibm_quantum')
            except Exception as e:
                raise RuntimeError(f"Failed to initialize IBM backends: {e}")
        
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

    def setUpSampler(self, backend):
        if (isinstance(backend, Backend)):
            print()
            return Sampler(mode = backend)

        else:
            raise TypeError(f"Backend is not of type {Backend}")
        