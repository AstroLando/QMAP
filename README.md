# QMAP
Qmap (ancronym) allows users to test small scale quantum computing tasks and see their effectiveness.

## Usage
After downloading the project, you can run it out of the box using the ```Test.py``` files out of the box. Ensure to use the right backend setup.

### IQM

```
b, s, n = PR.setUpIQM("BACKEND_NAME", "TOKEN")
```

Ensure to put in your token from the resonance platform.

### IBM

```
b, s, n = PR.setUpIBM("BACKEND_NAME", "TOKEN")
```

### Other Backend
You can use any other backend. Initialize your own backend, and insert the backend into the following:
```
 PR.runProblemSet(backend, sampler, name)
```
Ensure the backend is of type ```BackendV2``` (see ```qiskit.providers.backend```).

You can get the sampler using ```ProblemRunner.setUpSampler("BACKEND")```, inserting your backend of choice.

