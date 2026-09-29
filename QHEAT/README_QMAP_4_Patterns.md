# QMAP Hybrid Workflow Diagnostics

This directory contains four minimal hybrid quantum--classical workflow
diagnostics intended for QMAP:

1.  **QTES / Trotterized Hamiltonian Evolution** --- a high-locality,
    contiguous quantum execution example.
2.  **VQE / Pauli Expectation QOOL** --- a low-locality, fragmented
    workflow in which a classical optimizer repeatedly invokes a quantum
    expectation-value kernel.
3.  **QSMC / Quantum Sampling** --- a moderate-locality, batched
    workflow in which the QPU generates many samples before classical
    aggregation.
4.  **QASP / SKQD-Inspired Subspace Construction** --- a
    moderate-locality, batched workflow in which related Krylov-like
    quantum states are generated before a classical reduced-subspace
    solve.

The examples are intended to provide reproducible test cases for
characterizing hybrid dataflows, including circuit structure, QPU
invocations, classical--quantum synchronization, batching, quantum
residency, and eventually backend timing and I/O behavior.

## Requirements

The examples use Python 3, Qiskit, NumPy, and SciPy. The functional QSMC
simulator test additionally uses Qiskit Aer.

``` bash
pip install qiskit numpy scipy qiskit-aer
```

The initial tests run locally and do not require access to a QPU.

------------------------------------------------------------------------

## File Overview

``` text
qtes_trotter_ising.py          QTES problem definition
vqe_pauli_expectation.py       VQE/QOOL quantum-kernel definition
test_vqe_qool.py               Functional VQE/QOOL workflow
qsmc_sampling.py               QSMC sampling-kernel definition
test_qsmc_sampling.py          QSMC construction/sanity test
test_qsmc_workflow.py          Functional QSMC sampling + aggregation workflow
qasp_skqd.py                   QASP/SKQD-inspired problem definition
test_qasp_skqd.py              QASP construction/sanity test
test_qasp_skqd_workflow.py     Functional QASP subspace workflow
```

------------------------------------------------------------------------

## 1. QTES: Trotterized Hamiltonian Evolution

### Files

``` text
qtes_trotter_ising.py
```

The QTES example implements first-order Trotterized time evolution for a
one-dimensional transverse-field Ising Hamiltonian,

``` text
H = -J sum_i Z_i Z_(i+1) - h sum_i X_i
```

The workflow prepares an initial state, performs multiple Trotter steps
entirely within a contiguous quantum circuit, and measures the final
state.

### QELF classification

``` text
Pattern:            QTES
Locality:           High / contiguous
Classical role:     Model and parameter setup; final analysis
Quantum role:       State preparation and Hamiltonian time evolution
Logical QPU calls:  1 per execution
Synchronization:    Approximately 1 result-return boundary per execution
```

This provides the high-locality comparison case for the more fragmented
VQE/QOOL workflow and the batched QSMC/QASP workflows.

### Minimal usage

``` python
from qtes_trotter_ising import get_problem

problem = get_problem(
    num_qubits=6,
    trotter_steps=3,
    shots=1024,
)

qc = problem.build_circuit()

print(qc)
print("\nCircuit depth:", qc.depth())
print("Gate count:", qc.count_ops())

print("\nMetadata:")
for key, value in problem.get_metadata().items():
    print(f"  {key}: {value}")
```

This constructs and inspects the circuit but does not submit it to a
simulator or QPU.

### Parameters

``` python
problem = get_problem(
    num_qubits=6,
    trotter_steps=3,
    j_coupling=1.0,
    h_field=0.7,
    time=1.0,
    shots=1024,
)
```

For controlled QMAP comparisons, keep these parameters fixed across
backends whenever possible.

------------------------------------------------------------------------

## 2. VQE: Pauli Expectation Kernel and QOOL Workflow

### Files

``` text
vqe_pauli_expectation.py
test_vqe_qool.py
```

`vqe_pauli_expectation.py` defines the quantum kernel. It constructs a
parameterized hardware-efficient ansatz and a generic Pauli Hamiltonian.

`test_vqe_qool.py` adds a classical COBYLA optimizer around that kernel,
producing a complete minimal QOOL dataflow.

``` text
vqe_pauli_expectation.py  = one quantum objective-function evaluation
test_vqe_qool.py          = repeated evaluations inside a classical outer loop
```

### QELF classification

``` text
Pattern:            QOOL
Locality:           Low / fragmented
Classical role:     Parameter update and optimization
Quantum role:       Expectation-value/objective evaluator
Logical QPU calls:  Approximately one per objective evaluation
Synchronization:    Approximately one per objective evaluation
```

The defining dataflow is:

``` text
Classical optimizer
        |
        v
Parameter set
        |
        v
Quantum expectation evaluation
        |
        v
Energy / objective value
        |
        v
Classical parameter update
        |
        +--------------------> repeat
```

### Inspecting the VQE quantum kernel

``` python
from vqe_pauli_expectation import get_problem

problem = get_problem(
    num_qubits=4,
    layers=2,
    shots=1024,
)

qc = problem.build_circuit()
hamiltonian = problem.get_observables()

print(qc)
print("\nCircuit depth:", qc.depth())
print("Gate count:", qc.count_ops())

print("\nHamiltonian:")
print(hamiltonian)

print("\nMetadata:")
for key, value in problem.get_metadata().items():
    print(f"  {key}: {value}")
```

### Running the complete QOOL workflow

``` bash
python test_vqe_qool.py
```

The test uses Qiskit's `Statevector` implementation to evaluate the
expectation value and SciPy's COBYLA optimizer for the classical outer
loop. It reports the optimized energy, parameters, objective
evaluations, logical quantum-kernel invocations, and classical
synchronization points.

The statevector test is a **functional implementation of the QOOL
dataflow**, but not yet a physical hybrid QPU/HPC deployment. A reported
`qpu_call` represents a logical quantum-kernel invocation. Local
statevector execution does not include physical queueing, network
latency, hardware execution time, shot noise, or result-transfer
overhead.

------------------------------------------------------------------------

## 3. QSMC: Batched Quantum Sampling

### Files

``` text
qsmc_sampling.py
test_qsmc_sampling.py
test_qsmc_workflow.py
```

`qsmc_sampling.py` defines a generic parameterized quantum sampling
kernel that generates a correlated bitstring distribution.

`test_qsmc_sampling.py` verifies construction and metadata.

`test_qsmc_workflow.py` executes the sampling circuit using Qiskit Aer
and performs classical aggregation of the returned samples.

The diagnostic is intentionally generic rather than an implementation of
one specific scientific quantum Monte Carlo algorithm. Its purpose is to
expose the dataflow structure of a sampling-oriented QSMC pattern.

### QELF classification

``` text
Pattern:            QSMC
Locality:           Moderate / batched
Classical role:     Sample aggregation and statistical analysis
Quantum role:       Generation of samples from a correlated distribution
Logical QPU calls:  1 per sample batch
Synchronization:    Approximately 1 per returned sample batch
```

The defining dataflow is:

``` text
Classical sampling setup
          |
          v
+-----------------------+
| Quantum sample batch  |
|                       |
| sample                |
| sample                |
| ...                   |
| sample x N shots      |
+-----------------------+
          |
          v
Classical aggregation
          |
          v
Statistics / estimator
```

The important structural point is that `N` shots do **not** imply `N`
classical synchronization events. A large sample batch can be collected
within one logical QPU invocation and returned for subsequent classical
processing.

### Inspecting the QSMC kernel

``` python
from qsmc_sampling import get_problem

problem = get_problem(
    num_qubits=4,
    layers=2,
    shots=1024,
)

qc = problem.build_circuit()

print(qc)
print("\nCircuit depth:", qc.depth())
print("Gate count:", qc.count_ops())

print("\nMetadata:")
for key, value in problem.get_metadata().items():
    print(f"  {key}: {value}")
```

### Running the functional QSMC workflow

``` bash
python test_qsmc_workflow.py
```

This requires `qiskit-aer`. The workflow executes the sampling circuit,
collects the requested number of shots, converts counts to empirical
probabilities, and reports structural metrics such as:

``` text
logical_qpu_calls
classical_sync_points
samples_generated
samples_per_qpu_call
```

For QMAP experiments, a useful extension is to sweep the sample batch
size, for example:

``` text
100 shots
1,000 shots
10,000 shots
```

subject to backend limits. This allows measurement of how orchestration
and result-return costs are amortized as more quantum sampling work is
performed per classical synchronization point.

------------------------------------------------------------------------

## 4. QASP: SKQD-Inspired Quantum-Assisted Subspace Workflow

### Files

``` text
qasp_skqd.py
test_qasp_skqd.py
test_qasp_skqd_workflow.py
```

`qasp_skqd.py` defines an SKQD-inspired diagnostic that constructs a
batch of Krylov-like states,

``` text
|phi_k> = exp(-i H k*dt) |psi_0>
```

using Trotterized Hamiltonian evolution.

`test_qasp_skqd.py` verifies construction of the circuit batch.

`test_qasp_skqd_workflow.py` provides an end-to-end functional QASP
dataflow. In the current local implementation, ideal statevectors are
used to construct the projected overlap and Hamiltonian matrices, after
which SciPy performs the reduced classical eigensolve.

### QELF classification

``` text
Pattern:            QASP
Locality:           Moderate / batched
Classical role:     Subspace assembly and reduced eigensolve
Quantum role:       Krylov-state / subspace generation
Logical QPU calls:  1 conceptual batch where batching is supported
Quantum circuits:   krylov_dimension circuits in the initial diagnostic
Synchronization:    Approximately 1 batch-to-classical boundary
```

The defining dataflow is:

``` text
Classical problem setup
          |
          v
+-----------------------+
| Quantum subspace batch|
|                       |
| |phi_0>               |
| |phi_1>               |
| |phi_2>               |
| ...                   |
+-----------------------+
          |
          v
Construct projected H,S
          |
          v
Reduced classical solve
          |
          v
Eigenvalues / solution
```

### Inspecting the QASP/SKQD diagnostic

``` python
from qasp_skqd import get_problem

problem = get_problem(
    num_qubits=4,
    krylov_dimension=4,
    trotter_steps=2,
    evolution_step=0.2,
    shots=1024,
)

circuits = problem.build_circuits()

print(f"Generated {len(circuits)} Krylov-state circuits.\n")

for k, circuit in enumerate(circuits):
    print(f"Krylov state k = {k}")
    print("Circuit depth:", circuit.depth())
    print("Gate count:", circuit.count_ops())
    print()

print("Hamiltonian:")
print(problem.get_observables())

print("\nMetadata:")
for key, value in problem.get_metadata().items():
    print(f"  {key}: {value}")
```

### Running the functional QASP workflow

``` bash
python test_qasp_skqd_workflow.py
```

The local functional test:

1.  Generates the Krylov-like quantum states.
2.  Constructs the overlap matrix `S`.
3.  Constructs the projected Hamiltonian `H_sub`.
4.  Removes numerically dependent subspace directions when necessary.
5.  Solves the resulting reduced eigenvalue problem classically.
6.  Reports quantum-state-generation time, classical subspace-processing
    time, and structural QASP metrics.

This is a **functional deployment of the QASP dataflow**, but it should
not yet be interpreted as a hardware-complete SKQD implementation. The
local test obtains statevectors directly. A physical QPU would instead
require measurement procedures to estimate the projected Hamiltonian and
overlap information.

Conceptually:

``` text
Local diagnostic:
|phi_i> -> statevector -> H_ij, S_ij -> reduced solve

Hardware diagnostic:
|phi_i> -> measurement circuits/samples -> estimated H_ij, S_ij
        -> reduced solve
```

The hardware-compatible version will therefore introduce additional
physical circuit executions and provides an important quantity for QMAP
to measure.

------------------------------------------------------------------------

## Comparing All Four QELF Diagnostics

  ---------------------------------------------------------------------------------------
  Characteristic       VQE / QOOL     QSMC           QASP / SKQD           QTES
  -------------------- -------------- -------------- --------------------- --------------
  Primary quantum      Pauli          Repeated       Subspace-state        Hamiltonian
  operation            expectation    sampling       generation            evolution
                       evaluation                                          

  Classical--quantum   Optimize -\>   Sample batch   Quantum batch -\>     Execute -\>
  structure            execute -\>    -\> aggregate  reduced solve         return
                       return -\>                                          
                       repeat                                              

  Logical QPU          Repeated       Low / batched  Low / batched         Low
  invocations                                                              

  Synchronization      High           Moderate to    Moderate to low       Low
  frequency                           low                                  

  Quantum compute      Short          Sampling batch Subspace-generation   Extended
  region               objective                     batch                 evolution
                       evaluation                                          

  QELF locality        Fragmented     Batched        Batched               Contiguous
  ---------------------------------------------------------------------------------------

For an initial controlled comparison, a useful common baseline is:

``` text
Qubits: 4
Shots:  1024
```

Additional starting parameters:

``` text
VQE/QOOL:
    ansatz layers = 2
    fixed optimizer evaluation limit

QSMC:
    layers = 2
    sample batch = 1024 shots

QASP/SKQD:
    Krylov dimension = 4
    Trotter steps = 2
    evolution step = 0.2

QTES:
    fixed evolution time
    fixed Trotter-step count
```

The parameters do not make the four algorithms computationally
equivalent. They provide a consistent small-scale starting point for
comparing their execution structures.

------------------------------------------------------------------------

## Moving the Diagnostics to QMAP Backends

The next step is to preserve the workflow definitions while replacing
local simulator/statevector execution with the QMAP backend interface.

For each execution, record where available:

``` text
problem_name
pattern
backend
num_qubits
circuit_depth
gate_count
num_circuits
num_shots
logical_qpu_calls
physical_circuit_executions
classical_sync_points
submission_time
queue_time
compile_or_transpile_time
qpu_execution_time
result_return_time
payload_size_bytes
```

Pattern-specific quantities should also be retained:

``` text
VQE/QOOL:
    objective_evaluations
    optimizer_iterations
    Pauli measurement groups

QSMC:
    samples_generated
    samples_per_qpu_call
    sample_batch_size

QASP:
    krylov_dimension
    subspace matrix elements
    circuits per quantum batch

QTES:
    trotter_steps
    evolution_time
```

### Logical calls versus physical executions

This distinction is important across the diagnostics.

For VQE, one logical objective evaluation can require multiple physical
measurement circuits for noncommuting Pauli terms.

For QSMC, one logical batch can contain many shots of the same or
related sampling circuits.

For QASP, one conceptual subspace-generation batch contains multiple
Krylov-state circuits, and a hardware-compatible implementation can
require additional measurement circuits to estimate projected
Hamiltonian and overlap quantities.

For QTES, the initial diagnostic normally consists of one circuit
containing the complete state-preparation and Trotter-evolution region,
followed by measurement.

------------------------------------------------------------------------

## Experimental Goal

These examples are not intended primarily as application benchmarks.
They are diagnostic workloads for measuring how different hybrid
dataflow structures affect execution.

The primary comparison is therefore not simply:

``` text
Which algorithm runs faster?
```

but rather:

``` text
How do QPU execution, synchronization, orchestration, batching,
and quantum-resident compute regions differ between patterns?
```

The four diagnostics deliberately span three QELF locality structures:

``` text
Fragmented:
    VQE / QOOL

Batched:
    QSMC
    QASP / SKQD

Contiguous:
    QTES
```

Running the same diagnostic problems across QMAP-supported systems can
provide measured values for representative QELF locality characteristics
while also exposing which quantities are hardware-, runtime-, or
deployment-dependent.

The resulting measurements can be used to populate a quantitative
comparison of representative hybrid dataflows, including synchronization
frequency, logical and physical quantum executions, orchestration cost,
quantum execution time, and the degree to which work can be aggregated
within quantum-resident execution regions.

------------------------------------------------------------------------

## Recommended Initial Experiment Sequence

Run the diagnostics in the following order:

``` text
1. QTES       - simplest contiguous baseline
2. VQE/QOOL   - fragmented outer-loop comparison
3. QSMC       - batched sampling comparison
4. QASP/SKQD  - batched subspace-generation comparison
```

Begin with the local tests to verify circuit and workflow behavior. Then
replace the local execution layer with the same QMAP-supported backend
for all four diagnostics wherever possible. Keeping backend, qubit
count, shot count, and other applicable parameters controlled will make
the resulting timing and I/O measurements easier to compare.
