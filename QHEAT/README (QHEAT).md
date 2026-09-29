# QMAP Hybrid Workflow Diagnostics

This directory contains two minimal hybrid quantum--classical workflow
diagnostics intended for QMAP:

1.  **QTES / Trotterized Hamiltonian Evolution** --- a high-locality,
    contiguous quantum execution example.
2.  **VQE / Pauli Expectation QOOL** --- a low-locality, fragmented
    workflow in which a classical optimizer repeatedly invokes a quantum
    expectation-value kernel.

The examples are intended to provide reproducible test cases for
characterizing hybrid dataflows, including circuit structure, QPU
invocations, classical--quantum synchronization, and eventually backend
timing and I/O behavior.

## Requirements

The examples use Python 3 and Qiskit. The VQE/QOOL workflow also uses
NumPy and SciPy.

``` bash
pip install qiskit numpy scipy
```

The initial tests run locally and do not require access to a QPU.

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

This makes QTES useful as the high-locality comparison case for the more
fragmented VQE/QOOL workflow.

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

The default constructor supports:

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

The distinction is important:

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

This test verifies circuit and Hamiltonian construction without
performing the classical optimization.

### Running the complete QOOL workflow

Run:

``` bash
python test_vqe_qool.py
```

The test uses Qiskit's `Statevector` implementation to evaluate the
expectation value and SciPy's COBYLA optimizer for the classical outer
loop.

During execution, output should resemble:

``` text
Starting QOOL/VQE optimization
--------------------------------
Evaluation   1 | Energy = ...
Evaluation   2 | Energy = ...
Evaluation   3 | Energy = ...
...
```

At completion, the program reports the optimized energy, parameters, and
structural QOOL metrics such as:

``` text
objective_evaluations
qpu_calls
classical_sync_points
```

### Important interpretation

The statevector test is a **functional implementation of the QOOL
dataflow**, but it is not yet a physical hybrid QPU/HPC deployment.

In the local test, a reported `qpu_call` represents a **logical
quantum-kernel invocation**. Because `Statevector.from_instruction()`
executes locally, the test does not contain physical QPU queueing,
network latency, hardware execution time, shot noise, or result-transfer
overhead.

The purpose of the local version is to verify the workflow structure
before replacing the statevector evaluator with a QMAP backend execution
path.

------------------------------------------------------------------------

## Comparing QTES and QOOL

The two problems are deliberately complementary.

  -----------------------------------------------------------------------
  Characteristic          QTES                    VQE / QOOL
  ----------------------- ----------------------- -----------------------
  Primary quantum         Hamiltonian evolution   Pauli expectation
  operation                                       evaluation

  Classical--quantum      Execute, then return    Optimize → execute →
  structure                                       return → repeat

  Logical QPU invocations Low                     Repeated

  Synchronization         Low                     High
  frequency                                       

  Quantum compute region  Extended evolution      Short objective
                                                  evaluation

  QELF locality           Contiguous              Fragmented
  -----------------------------------------------------------------------

For an initial comparison, useful common settings are:

``` text
Qubits: 4
Shots:  1024
```

For VQE, use two ansatz layers and a fixed optimizer evaluation limit.
For QTES, use a fixed evolution time and Trotter-step count.

------------------------------------------------------------------------

## Moving the Diagnostics to QMAP Backends

The next step is to preserve the workflow definitions while replacing
local execution with the QMAP backend interface.

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

A particularly important distinction for VQE is between a **logical QPU
call** and **physical circuit executions**. One VQE energy evaluation is
logically one invocation of the quantum kernel, but a Hamiltonian
containing noncommuting Pauli terms can require multiple measurement
circuits or measurement bases. Backend grouping and execution strategies
can therefore produce multiple physical executions for a single logical
objective evaluation.

For QTES, the initial diagnostic should normally consist of one circuit
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
How do QPU execution, synchronization, orchestration, and
quantum-resident compute regions differ between patterns?
```

Running the same diagnostic problems across QMAP-supported systems can
provide measured values for representative QELF locality characteristics
while also exposing which quantities are hardware-, runtime-, or
deployment-dependent.

## Planned Extensions

The next candidate problems are:

``` text
QSMC  - repeated quantum sampling / Monte Carlo diagnostic
QASP  - SKQD-style subspace construction and matrix-element estimation
```

Together with QTES and VQE/QOOL, these provide representative examples
spanning contiguous, batched, and fragmented hybrid execution
structures.
