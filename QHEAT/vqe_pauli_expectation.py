# vqe_pauli_expectation.py

import numpy as np

from qiskit import QuantumCircuit
from qiskit.circuit import ParameterVector
from qiskit.quantum_info import SparsePauliOp


class VQEPauliExpectation:
    """
    VQE diagnostic problem:
    Parameterized ansatz + Pauli expectation-value estimation.

    Pattern: QOOL
    Locality: Low / fragmented

    Purpose:
        Represent the quantum evaluation kernel inside a VQE outer loop.
        A classical optimizer supplies parameters, the QPU evaluates
        expectation values, and the results return to the classical side
        before the next parameter update.
    """

    name = "vqe_pauli_expectation"
    pattern = "QOOL"

    def __init__(
        self,
        num_qubits: int = 4,
        layers: int = 2,
        shots: int = 1024,
        parameters=None,
    ):
        self.num_qubits = num_qubits
        self.layers = layers
        self.shots = shots

        # Two Ry parameters per qubit per layer.
        self.theta = ParameterVector(
            "theta",
            length=num_qubits * layers
        )

        if parameters is None:
            # Deterministic defaults make QMAP runs reproducible.
            self.parameters = np.linspace(
                0.1,
                1.0,
                len(self.theta)
            )
        else:
            if len(parameters) != len(self.theta):
                raise ValueError(
                    f"Expected {len(self.theta)} parameters, "
                    f"received {len(parameters)}."
                )
            self.parameters = np.asarray(parameters, dtype=float)

    def build_ansatz(self) -> QuantumCircuit:
        """
        Construct a simple hardware-efficient parameterized ansatz.

        Each layer contains:
            Ry rotations
            nearest-neighbor CX entanglement

        This is intentionally generic rather than chemistry-specific,
        allowing the same diagnostic to run across QMAP backends.
        """

        qc = QuantumCircuit(self.num_qubits)

        p = 0

        for _ in range(self.layers):

            # Parameterized single-qubit rotations
            for q in range(self.num_qubits):
                qc.ry(self.theta[p], q)
                p += 1

            # Linear nearest-neighbor entanglement
            for q in range(self.num_qubits - 1):
                qc.cx(q, q + 1)

        return qc

    def build_hamiltonian(self) -> SparsePauliOp:
        """
        Construct a small generic Pauli Hamiltonian.

        H = sum_i a_i Z_i
            + sum_i b_i Z_i Z_{i+1}
            + sum_i c_i X_i

        The objective is not to model a particular molecule, but to
        provide representative Pauli expectation measurements for
        characterizing the VQE/QOOL dataflow.
        """

        terms = []

        # Local Z terms
        for q in range(self.num_qubits):
            pauli = ["I"] * self.num_qubits
            pauli[self.num_qubits - 1 - q] = "Z"

            terms.append(
                ("".join(pauli), 0.5)
            )

        # Nearest-neighbor ZZ terms
        for q in range(self.num_qubits - 1):
            pauli = ["I"] * self.num_qubits
            pauli[self.num_qubits - 1 - q] = "Z"
            pauli[self.num_qubits - 2 - q] = "Z"

            terms.append(
                ("".join(pauli), 0.25)
            )

        # Local X terms
        for q in range(self.num_qubits):
            pauli = ["I"] * self.num_qubits
            pauli[self.num_qubits - 1 - q] = "X"

            terms.append(
                ("".join(pauli), 0.1)
            )

        return SparsePauliOp.from_list(terms)

    def build_circuit(self) -> QuantumCircuit:
        """
        Return the parameter-bound ansatz circuit.

        Measurement basis rotations are intentionally left to the
        backend / expectation-value execution layer.
        """

        qc = self.build_ansatz()

        bindings = {
            self.theta[i]: self.parameters[i]
            for i in range(len(self.theta))
        }

        return qc.assign_parameters(bindings)

    def get_observables(self):
        """
        Return the Pauli observables required for the energy estimate.
        """
        return self.build_hamiltonian()

    def get_metadata(self) -> dict:
        """
        Metadata useful for QMAP timing and dataflow characterization.
        """

        num_pauli_terms = len(self.build_hamiltonian())

        return {
            "problem_name": self.name,
            "pattern": self.pattern,

            "num_qubits": self.num_qubits,
            "ansatz_layers": self.layers,
            "shots": self.shots,
            "num_parameters": len(self.theta),
            "num_pauli_terms": num_pauli_terms,

            "locality_class": "fragmented",

            # Per objective-function evaluation:
            "expected_classical_sync_points": 1,

            # Logical call. Physical circuit count may be larger because
            # Pauli terms require multiple measurement bases.
            "expected_qpu_calls": 1,

            "quantum_compute_region":
                "parameterized ansatz + Pauli expectation evaluation",

            "classical_role":
                "parameter update / outer-loop optimization",

            "quantum_role":
                "objective-function expectation evaluation",
        }


def get_problem(**kwargs):
    """
    Factory function for QMAP-style dynamic loading.
    """
    return VQEPauliExpectation(**kwargs)
