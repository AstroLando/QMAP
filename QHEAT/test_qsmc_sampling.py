from qsmc_sampling import get_problem


problem = get_problem(
    num_qubits=4,
    layers=2,
    shots=1024,
)

qc = problem.build_circuit()

print(qc)

print("\nCircuit depth:")
print(qc.depth())

print("\nGate count:")
print(qc.count_ops())

print("\nMetadata:")
for key, value in problem.get_metadata().items():
    print(f"  {key}: {value}")
