# QMAP

**QMAP** (acronym) allows users to test small-scale quantum computing tasks and evaluate their effectiveness across different backends.

## Usage

After downloading the project, you can run it using the `Test.py` files. Make sure to configure the appropriate backend setup.

### IQM

```python
PR.runProblemSet(*PR.setUpIQM("BACKEND_NAME", "TOKEN"))
```

> ⚠️ **Important:** Use your token from the **IQM Resonance** platform.

### IBM

```python
PR.runProblemSet(*PR.setUpIBM("BACKEND_NAME", "TOKEN"))
```

> ⚠️ **Important:** Use your token from **IBM Quantum**, *not* the IBM Cloud platform.  
> The code currently uses the `ibm_quantum` channel.

## Other Backends

You can use any compatible backend. Initialize your backend and pass it in manually:

```python
PR.runProblemSet(backend, sampler, name)
```

Ensure the backend is of type `BackendV2` (from `qiskit.providers.backend`).

You can get a sampler using:

```python
ProblemRunner.setUpSampler(backend)
```

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
IBMservice.backend("ibm_<BACKENDNAME>")
```

> ⚠️ **Important:** You must add backends *before* calling `setUpIBM`, as `IBMService` requires a valid user token at initialization.