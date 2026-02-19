# QMAP: Quantum Monitoring and Analysis Platform

QMAP is a benchmarking and analysis suite designed to evaluate quantum algorithm performance across multiple hardware vendors and simulators, including IBM, IQM, Quantinuum, and IonQ. It features atomic data persistence and precise server-side latency tracking.

## Repository Structure

The project is organized into a core package and supporting directories for research data and visualization:

```text
.
├── docs/                # Setup guides and legacy documentation
├── plots/               # Jupyter notebooks for results visualization
├── results/             # CSV output from hardware/simulator runs
├── src/
│   ├── qmap/            # Core Package
│   │   ├── main.py      # Entry point for running benchmarks
│   │   ├── config.yml   # Experiment configurations (batch runs)
│   │   ├── ProblemRunner.py # Execution engine and data persistence
│   │   ├── utils.py     # Shared helper functions
│   │   └── problems/    # Algorithm implementations
│   │       ├── ProblemBase.py # Abstract base for all algorithms
│   │       ├── BV.py     # Bernstein-Vazirani
│   │       ├── Grovers.py # Grover's Algorithm
│   │       ├── QFT.py     # Quantum Fourier Transform
│   │       ├── QPE.py     # Quantum Phase Estimation
│   │       └── RNG.py     # Random Number Generator
│   └── tests/           # Validation and experiment scripts
├── tokens.env           # API Tokens (IBM, IonQ, etc.)
├── pyproject.toml       # Dependencies (Qiskit 2.x, qnexus, etc.)
└── README.md
```

## Features
* **Multi-Vendor Support**: Integrated setup for IBM Quantum, IQM Resonance, Quantinuum Nexus, and IonQ.
* **Atomic Persistence**: Results are written to CSV immediately after every repetition, preventing data loss during long QPU queues.
* **Server-Side Tracking**: Captures official job_id, created_time, and end_time directly from vendor APIs to isolate QPU latency from network noise.
* **Dynamic Configuration**: Batch process multiple algorithms with unique parameters (reps, qubits, shots) via a single config.yml.
* **Noisy Emulation**: Automatic mapping of IonQ hardware targets (Aria, Forte) to noisy simulators when specified in configuration.

## Setup

1. **Dependencies**: Install the required packages using uv or pip:
```bash
pip install .
```

2. **Authentication**: Add your API tokens to tokens.env in the root directory:
```bash
IBM_TOKEN=your_token_here
IONQ_TOKEN=your_token_here
```

3. **Configuration**: Define your experiment suite in `src/qmap/config.yml`.

## Usage

Run the benchmarking suite from the project root:
```bash
python src/qmap/main.py
```

## Data Format

Results are stored in `results/` with the naming convention `{backend}_{date}.csv`. Each file includes:
* `problem`: Algorithm name or nickname.
* `job_id`: Unique identifier from the provider.
* `created_time`: Timestamp of when the job entered the QPU queue.
* `time_ms`: Total execution time.
* `error_data`: Qubit calibration metrics (T1, T2, readout error) at time of execution.


---

## Setup 

### 1. Set Up Virtual Environment

Ensure that you have the [uv](https://docs.astral.sh/uv/) Python package manager installed on your device.

In the root directory of this project, run `uv sync`. This will install all of the packages needed for the project. 
You shouldn't need to change anything. This package manager is really good about ensuring portability to different OS.

> If an error occurs with dependencies, run `uv python pin 3.12` before running `uv sync`. This should resolve the issue.

Start virtual environment by running `source .venv/bin/activate`. Environment is called `qmap`. You should see something like the following in your terminal if it activated correctly:
```bash
(qmap) path/to/QMAP $ 
```

### 2. Set Up API tokens for Quantum Platforms

Create the file `tokens.env` and place this in QMAP's root directory (e.g. `$PATH/TO/QMAP/tokens.env`).

Here are some fields to put inside the tokens. Adjust as needed.

```bash
IBM_TOKEN="ibm_token"
IBM_INSTANCE="instance_name"

IQM_TOKEN="iqm_token"

QUANTINUUM_TOKEN="quantinuum_token"
```

### 3. Verify Tokens Work

Run the following commands in your terminal to verify that your tokens work. If you do not have certain vendors in this
list, please skip them.
* For IBM, the token & instance will be read from `IBM_TOKEN` & `IBM_INSTANCE` environment variables in `tokens.env`.
* For Quantinuum, there is no token, but you will be prompted to enter your email and password to log in.
* For IQM, the token will automatically be read from environment variable `IQM_TOKEN` in `tokens.env`, so nothing no code needs to be included. 

```zsh
# IBM Token
python -c "from qiskit_ibm_runtime import QiskitRuntimeService; from dotenv import load_dotenv; import os; \
load_dotenv('tokens.env'); \
service = QiskitRuntimeService(channel='ibm_cloud', token=os.environ['IBM_TOKEN'], instance=os.environ['IBM_INSTANCE']); \
print(service.usage())"

# Quantinuum Authentication
python -c "import qnexus as qnx; qnx.login_with_credentials(); qnx.devices.get_all().df()"
```

### 4. Run Light Benchmark
To verify that the benchmark will work on all platforms, first make any configurations to the `config.yml` in the project's root path. Adjust so that you run a very small experiment just to verify that everything is working as it should with the login credentials. 
> **NOTE:** Currently this will only run 1 experiment at a time on a specific vendor's machine.  

Next, run `uv run python -m src.tests.lightTest` from the root path of the project to execute the lightweight benchmark that performs Random Number Generation, Quantum Fourier Transform, Bernstein-Vazirani, Grover's, & Quantum Phase Estimation as the experiments. 

> **TODO:** Add GHZ benchmark class to the list of programs and add to all the tests.

#### Vendor Backends
To see what backends are available to you, you will have to log in to the following platforms. They are available based on your project's plan.
* IQM -> [IQM Resonance](https://resonance.meetiqm.com/)
* IBM -> [IBM Quantum](https://quantum.cloud.ibm.com/computers)
* Quantinuum -> [Nexus Portal](https://nexus.quantinuum.com/backends)
* IonQ -> [Hardware & Simulators](https://cloud.ionq.com/backends)