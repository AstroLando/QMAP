# QMAP: Quantum Metric Assessment Platform

QMAP is a benchmarking and analysis suite designed to evaluate quantum algorithm performance across multiple hardware vendors and simulators, including IBM, IQM, Quantinuum, and IonQ. It features atomic data persistence and precise server-side latency tracking.

## Repository Structure

The project is organized into a core package and supporting directories for research data and visualization:

```bash
QMAP/
├── docs/                       # Setup guides and legacy documentation
├── envs/                       # Conda environment YAML files for each vendor
├── plots/                      # Jupyter notebooks for results visualization
├── results/                    # CSV output from hardware/simulator runs
├── src/
│   ├── qmap/                   # Core Package
│   │   ├── main.py             # Entry point for running benchmarks
│   │   ├── config.yml          # Experiment configurations (batch runs)
│   │   ├── ProblemRunner.py    # Execution engine and data persistence
│   │   ├── utils.py            # Shared helper functions
│   │   └── problems/           # Algorithm implementations
│   │       ├── ProblemBase.py  # Abstract base for all algorithms
│   │       ├── BV.py           # Bernstein-Vazirani
│   │       ├── Grovers.py      # Grover's Algorithm
│   │       ├── QFT.py          # Quantum Fourier Transform
│   │       ├── QPE.py          # Quantum Phase Estimation
│   │       └── RNG.py          # Random Number Generator
│   └── tests/                  # Validation and experiment scripts
├── tokens.env                  # API Tokens (IBM, IonQ, etc.)
├── pyproject.toml              # Build configuration for local src mapping
├── setup_envs.sh               # Automated Conda environment builder
└── README.md
```

## Features
* **Multi-Vendor Support**: Integrated setup for IBM Quantum, IQM Resonance, Quantinuum Nexus, and IonQ.
* **Isolated Dependency Management**: Uses isolated Conda environments to prevent Qiskit version conflicts between vendors.
* **Atomic Persistence**: Results are written to CSV immediately after every repetition, preventing data loss during long QPU queues.
* **Server-Side Tracking**: Captures official `job_id`, `created_time`, and `end_time` directly from vendor APIs to isolate QPU latency from network noise.
* **Dynamic Configuration**: Batch process multiple algorithms with unique parameters (reps, qubits, shots) via a single `config.yml`.
* **Noisy Emulation**: Automatic mapping of IonQ hardware targets (Aria, Forte) to noisy simulators when specified in configuration.

## Requirements

* Python 3.11 (Managed automatically via Conda)
* Miniconda or Anaconda

## Setup Guide

### 1. Build Isolated Conda Environments

Because quantum vendor SDKs often have conflicting dependency requirements (e.g., Qiskit 1.x vs 2.x), QMAP isolates each vendor into its own environment.

From the root directory of the project, make the setup script executable and run it:
```bash
chmod +x setup_envs.sh
./setup_envs.sh
```

This script will parse the YAML files in the `envs/` directory, build the environments, and automatically link the `src/` code. It will create four distinct environments:
* `qmap_ibm`
* `qmap_iqm`
* `qmap_ionq`
* `qmap_quantinuum`

#### Useful Script Commands:

* `./setup_envs.sh -h`: View the help menu and options.
* `./setup_envs.sh --force`: Nuke and rebuild all environments from scratch.
* `./setup_envs.sh --force <vendor>`: Rebuild only a specific vendor's environment (`<vendor>`: `ibm`, `iqm`, `ionq`, `quantinuum`)

When you are ready to work, activate the environment for the vendor you are targeting:
```bash
conda activate qmap_ibm
```

### 2. Set Up API tokens for Quantum Platforms

Create a file named `tokens.env` in QMAP's root directory. Add your API credentials here. Adjust as needed based on which platforms you are benchmarking:

```bash
IBM_TOKEN="ibm_token"
IBM_INSTANCE="instance_name"

IQM_TOKEN="iqm_token"
IQM_ONPREM_TOKEN="ornl_token"

QUANTINUUM_TOKEN="quantinuum_token"
```

### 3. Verify Tokens Work
Activate the corresponding Conda environment, then run the following commands in your terminal to verify your authentication. Skip the vendors you do not have access to.

* For IBM, the token & instance will be read from `IBM_TOKEN` & `IBM_INSTANCE` in `tokens.env`.
* For Quantinuum, you will be prompted to enter your email and password in the terminal to log in.
* For IQM, the token will automatically be read from `IQM_TOKEN` in `tokens.env`.

```bash
# Verify IBM (Run inside qmap_ibm)
python -c "from qiskit_ibm_runtime import QiskitRuntimeService; from dotenv import load_dotenv; import os; \
load_dotenv('tokens.env'); \
service = QiskitRuntimeService(channel='ibm_cloud', token=os.environ['IBM_TOKEN'], instance=os.environ['IBM_INSTANCE']); \
print(service.usage())"

# Verify Quantinuum (Run inside qmap_quantinuum)
python -c "import qnexus as qnx; qnx.login_with_credentials(); print(qnx.devices.get_all().df())"
```

### 4. Run Light Benchmark
To verify the benchmark suite executes correctly, adjust your `config.yml` in the root path for a very small experiment.
> NOTE: Currently this will only run 1 experiment at a time on a specific vendor's machine.

Activate the environment for the vendor & problems you configured, then execute the benchmark:
```bash
conda activate qmap_<vendor>
python -m src.tests.run_exps
```
This executes Random Number Generation, Quantum Fourier Transform, Bernstein-Vazirani, Grover's, & Quantum Phase Estimation.
> TODO: Add GHZ benchmark class to the list of programs and add to all the tests.

#### Vendor Backends
To see what backends are available to you, you will have to log in to the following platforms. They are available based on your project's plan.
* IQM -> [IQM Resonance](https://resonance.meetiqm.com/)
* IBM -> [IBM Quantum](https://quantum.cloud.ibm.com/computers)
* Quantinuum -> [Nexus Portal](https://nexus.quantinuum.com/backends)
* IonQ -> [Hardware & Simulators](https://cloud.ionq.com/backends)


## Usage
For full batch benchmarking, configure `config.yml` and run the main entry point:
```bash
conda activate qmap_<vendor>
python -m src.qmap.main
```

## Data Format

Results are stored in `results/` with the naming convention `{backend}_{date}.csv`. Each file includes:
* `problem`: Algorithm name or nickname.
* `job_id`: Unique identifier from the provider.
* `created_time`: Timestamp of when the job entered the QPU queue.
* `time_ms`: Total execution time.
* `error_data`: Qubit calibration metrics (T1, T2, readout error) at time of execution.

