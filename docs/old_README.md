# QMAP (outdated - will update soon)

**QMAP** (acronym) allows users to test small-scale quantum computing tasks and evaluate their effectiveness across different backends.

## Usage

After downloading the project, you can run it using the `Test.py` files. Make sure to configure the appropriate backend setup.

### IQM

```python
PR.runProblemSet(*PR.setUpIQM("BACKEND_NAME", "TOKEN"))
```

> Use your token from the **IQM Resonance** platform.

### IBM

```python
PR.runProblemSet(*PR.setUpIBM("BACKEND_NAME", "TOKEN"))
```

> Use your token from **IBM Quantum**, *not* the IBM Cloud platform.  
> The code currently uses the `ibm_quantum` channel.

### Quantinuum

```python
PR.runProblemSet(*PR.setUpQuantinuum("BACKEND_NAME"))
```

> Quantinuum requires the user to login via the terminal each time you run the code

## Other Backends

You can use any compatible backend. Initialize your backend and pass it in manually:

```python
PR.runProblemSet(backend, sampler, name, backendType)
```

Ensure the backend is of type `BackendV2` (from `qiskit.providers.backend`).

You can get a sampler using:

```python
ProblemRunner.setUpSampler(backend)
```

> Currently, supported backendType should be "IQM", "IBM", or "Quantinuum".  

## Adding Your Own Backends

You can extend the backend support by modifying `problemRunner.py`.

### Adding IQM Backends

In the `__init__` function, locate the `IQMdict`:

```python
self.IQMdict = {
    "garnet": "https://cocos.resonance.meetiqm.com/garnet",
    ...
}
```

Add your backend by specifying a name and its URL.

### Adding IBM Backends

In the `setUpIBM` function, locate the IBM backend dictionary:

```python
if not hasattr(self, 'IBMDict'):
            self.IBMDict = {
                "leastBusy" : IBMservice.least_busy(operational=True),...
```
Add your backend using:

```python
"backendNickname" : IBMservice.backend("ibm_<BACKENDNAME>")
```

> ⚠️ **Important:** You must add backends *before* calling `setUpIBM`, as `IBMService` requires a valid user token at initialization.

### Adding IQM Backends

In the `__init__` function, locate the `QuantinuumDict`:

```python
self.QuantinuumDict = {
            "H1-1E" : 'H1-1E', 
            "H1-1SC" : 'H1-1SC',
            ...
```

Add your backend by specifying a name the name, and the name again. The items before the colon are the input names, so you can use whatever you like, but the item after *must* match the name of the quantinuum backend.

> You can see a list of available backends using ```QuantinuumBackend.available_devices()```