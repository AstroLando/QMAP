# test_qasp_skqd_workflow.py

import time
import numpy as np

from scipy.linalg import eigh
from qiskit.quantum_info import Statevector

from qasp_skqd import get_problem


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

NUM_QUBITS = 4
KRYLOV_DIMENSION = 4
TROTTER_STEPS = 2
EVOLUTION_STEP = 0.2
SHOTS = 1024


# ------------------------------------------------------------
# Structural metrics
# ------------------------------------------------------------

metrics = {
    "logical_qpu_calls": 0,
    "quantum_circuits": 0,
    "classical_sync_points": 0,
    "krylov_states_generated": 0,
}


# ------------------------------------------------------------
# Create QASP / SKQD problem
# ------------------------------------------------------------

problem = get_problem(
    num_qubits=NUM_QUBITS,
    krylov_dimension=KRYLOV_DIMENSION,
    trotter_steps=TROTTER_STEPS,
    evolution_step=EVOLUTION_STEP,
    shots=SHOTS,
)

hamiltonian = problem.get_observables()


# ------------------------------------------------------------
# Generate quantum Krylov states
# ------------------------------------------------------------

print("\nQASP / SKQD workflow")
print("--------------------------------")

print(
    f"Generating {KRYLOV_DIMENSION} "
    "Krylov states as one logical batch..."
)

quantum_start = time.perf_counter()

states = []

metrics["logical_qpu_calls"] += 1


for k in range(KRYLOV_DIMENSION):

    # build_krylov_circuit() contains measurements because it is
    # intended for hardware execution. Statevector simulation
    # requires the unitary portion only.
    circuit = problem.build_krylov_circuit(k)

    circuit.remove_final_measurements()

    state = Statevector.from_instruction(circuit)

    states.append(state)

    metrics["quantum_circuits"] += 1
    metrics["krylov_states_generated"] += 1

    print(
        f"  Generated |phi_{k}> "
        f"(depth = {circuit.depth()})"
    )


quantum_end = time.perf_counter()

# The batch of quantum-derived information is now returned
# to the classical processing stage.

metrics["classical_sync_points"] += 1


# ------------------------------------------------------------
# Construct projected subspace matrices
# ------------------------------------------------------------

print("\nConstructing projected matrices...")

classical_start = time.perf_counter()

dimension = KRYLOV_DIMENSION

S = np.zeros(
    (dimension, dimension),
    dtype=complex,
)

H_sub = np.zeros(
    (dimension, dimension),
    dtype=complex,
)


for i in range(dimension):

    psi_i = states[i]

    for j in range(dimension):

        psi_j = states[j]

        # Overlap matrix:
        #
        # S_ij = <phi_i | phi_j>

        S[i, j] = np.vdot(
            psi_i.data,
            psi_j.data,
        )

        # Projected Hamiltonian:
        #
        # H_ij = <phi_i | H | phi_j>

        h_psi_j = hamiltonian.to_matrix() @ psi_j.data

        H_sub[i, j] = np.vdot(
            psi_i.data,
            h_psi_j,
        )


# ------------------------------------------------------------
# Stabilize the generalized eigenproblem
# ------------------------------------------------------------

# Numerical noise or near-linear dependence among Krylov states
# can make S poorly conditioned. Diagonalize S and retain only
# sufficiently significant subspace directions.

s_values, s_vectors = np.linalg.eigh(S)

threshold = 1e-10

keep = s_values > threshold

if np.count_nonzero(keep) == 0:
    raise RuntimeError(
        "No linearly independent Krylov states remain."
    )


print(
    "Effective subspace dimension:",
    np.count_nonzero(keep),
)


# Build an orthonormalized subspace transformation:
#
# X = V S^(-1/2)

X = (
    s_vectors[:, keep]
    @ np.diag(
        1.0 / np.sqrt(s_values[keep])
    )
)


# Transform projected Hamiltonian into orthonormal basis.

H_ortho = (
    X.conj().T
    @ H_sub
    @ X
)


# ------------------------------------------------------------
# Classical reduced solve
# ------------------------------------------------------------

eigenvalues, eigenvectors = eigh(H_ortho)

ground_energy = np.real(eigenvalues[0])

classical_end = time.perf_counter()


# ------------------------------------------------------------
# Results
# ------------------------------------------------------------

print("\nProjected overlap matrix S")
print("--------------------------------")

print(
    np.real_if_close(S)
)


print("\nProjected Hamiltonian H")
print("--------------------------------")

print(
    np.real_if_close(H_sub)
)


print("\nReduced eigenvalues")
print("--------------------------------")

for i, energy in enumerate(eigenvalues):

    print(
        f"{i}: {np.real(energy):.8f}"
    )


print("\nEstimated ground-state energy")
print("--------------------------------")

print(
    f"{ground_energy:.8f}"
)


# ------------------------------------------------------------
# Timing
# ------------------------------------------------------------

quantum_time = (
    quantum_end -
    quantum_start
)

classical_time = (
    classical_end -
    classical_start
)


print("\nTiming")
print("--------------------------------")

print(
    f"Quantum-state generation: "
    f"{quantum_time:.6f} s"
)

print(
    f"Classical subspace processing: "
    f"{classical_time:.6f} s"
)

print(
    f"Total diagnostic time: "
    f"{quantum_time + classical_time:.6f} s"
)


# ------------------------------------------------------------
# QASP structural metrics
# ------------------------------------------------------------

print("\nQASP Dataflow Metrics")
print("--------------------------------")

for key, value in metrics.items():
    print(
        f"{key}: {value}"
    )


print("\nClassification")
print("--------------------------------")

print("Pattern: QASP")
print("Locality: Batched")

print(
    "Quantum role: "
    "Krylov-state / subspace generation"
)

print(
    "Classical role: "
    "projected matrix assembly + reduced eigensolve"
)
