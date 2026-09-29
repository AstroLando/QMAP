# test_qsmc_workflow.py

from qiskit_aer import AerSimulator

from qsmc_sampling import get_problem


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

NUM_QUBITS = 4
LAYERS = 2
SHOTS = 1024


# ------------------------------------------------------------
# Create QSMC problem
# ------------------------------------------------------------

problem = get_problem(
    num_qubits=NUM_QUBITS,
    layers=LAYERS,
    shots=SHOTS,
)

circuit = problem.build_circuit()


# ------------------------------------------------------------
# Quantum sampling stage
# ------------------------------------------------------------

simulator = AerSimulator()

job = simulator.run(
    circuit,
    shots=SHOTS
)

result = job.result()

counts = result.get_counts()


# ------------------------------------------------------------
# Classical aggregation stage
# ------------------------------------------------------------

total_samples = sum(counts.values())

probabilities = {
    bitstring: count / total_samples
    for bitstring, count in counts.items()
}


# ------------------------------------------------------------
# Results
# ------------------------------------------------------------

print("\nQSMC Sampling Results")
print("--------------------------------")

for bitstring, count in sorted(
    counts.items(),
    key=lambda x: x[1],
    reverse=True
):
    print(
        f"{bitstring}: "
        f"{count:5d} samples | "
        f"P = {probabilities[bitstring]:.4f}"
    )


# ------------------------------------------------------------
# Structural metrics
# ------------------------------------------------------------

print("\nQSMC Dataflow Metrics")
print("--------------------------------")

print(f"logical_qpu_calls: 1")
print(f"classical_sync_points: 1")
print(f"samples_generated: {total_samples}")
print(f"samples_per_qpu_call: {total_samples}")

print("\nClassification")
print("--------------------------------")

print("Pattern: QSMC")
print("Locality: Batched")
print("Quantum role: sample generation")
print("Classical role: aggregation / statistical analysis")
