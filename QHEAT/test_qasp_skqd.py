# test_qasp_skqd.py

from qasp_skqd import get_problem


problem = get_problem(
    num_qubits=4,
    krylov_dimension=4,
    trotter_steps=2,
    evolution_step=0.2,
    shots=1024,
)

circuits = problem.build_circuits()

print(
    f"Generated {len(circuits)} "
    "Krylov-state circuits.\n"
)

for k, circuit in enumerate(circuits):

    print(f"Krylov state k = {k}")
    print("------------------------")

    print(circuit)

    print(
        "Circuit depth:",
        circuit.depth()
    )

    print(
        "Gate count:",
        circuit.count_ops()
    )

    print()


print("Hamiltonian:")
print(problem.get_observables())


print("\nMetadata:")

for key, value in (
    problem.get_metadata().items()
):
    print(f"  {key}: {value}")
