# qasp_skqd.py

import numpy as np

from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp


class QASPSKQD:
    """
    QASP diagnostic problem:
    SKQD-inspired quantum-assisted subspace construction.

    Pattern: QASP
    Locality: Moderate / batched

    Purpose:
        Generate a batch of Krylov-like quantum states that provide
        information for a reduced classical subspace problem.

        The quantum stage performs repeated state preparation and
        Hamiltonian evolution. The resulting measurements are then
        returned as a batch for classical assembly and analysis.

    This is intentionally a structural QASP/SKQD diagnostic rather
    than a complete production implementation of SKQD.
    """

    name = "qasp_skqd"
    pattern = "QASP"

    def __init__(
        self,
        num_qubits: int = 4,
        krylov_dimension: int = 4,
        trotter_steps: int = 2,
        evolution_step: float = 0.2,
        j_coupling: float = 1.0,
        h_field: float = 0.7,
        shots: int = 1024,
    ):
        self.num_qubits = num_qubits
        self.krylov_dimension = krylov_dimension
        self.trotter_steps = trotter_steps
        self.evolution_step = evolution_step
        self.j_coupling = j_coupling
        self.h_field = h_field
        self.shots = shots

    def build_hamiltonian(self) -> SparsePauliOp:
        """
        Construct the same general Ising-type Hamiltonian used
        for the time-evolution diagnostic.

        H = -J sum_i Z_i Z_(i+1) - h sum_i X_i
        """

        terms = []

        # ZZ interactions
        for q in range(self.num_qubits - 1):
            pauli = ["I"] * self.num_qubits

            pauli[self.num_qubits - 1 - q] = "Z"
            pauli[self.num_qubits - 2 - q] = "Z"

            terms.append(
                ("".join(pauli), -self.j_coupling)
            )

        # Transverse X field
        for q in range(self.num_qubits):
            pauli = ["I"] * self.num_qubits

            pauli[self.num_qubits - 1 - q] = "X"

            terms.append(
                ("".join(pauli), -self.h_field)
            )

        return SparsePauliOp.from_list(terms)

    def _zz_evolution(
        self,
        qc: QuantumCircuit,
        q0: int,
        q1: int,
        theta: float,
    ):
        """
        Implement a ZZ evolution term.
        """

        qc.cx(q0, q1)
        qc.rz(2.0 * theta, q1)
        qc.cx(q0, q1)

    def _trotter_step(
        self,
        qc: QuantumCircuit,
        dt: float,
    ):
        """
        Apply one first-order Trotter step.
        """

        # ZZ interaction
        for q in range(self.num_qubits - 1):
            self._zz_evolution(
                qc,
                q,
                q + 1,
                self.j_coupling * dt,
            )

        # X field
        for q in range(self.num_qubits):
            qc.rx(
                2.0 * self.h_field * dt,
                q,
            )

    def build_krylov_circuit(
        self,
        krylov_index: int,
    ) -> QuantumCircuit:
        """
        Construct one Krylov-like state

            |phi_k> = exp(-i H k*dt) |psi_0>

        using first-order Trotterization.
        """

        if krylov_index < 0:
            raise ValueError(
                "krylov_index must be non-negative."
            )

        qc = QuantumCircuit(
            self.num_qubits,
            self.num_qubits,
        )

        # Simple reproducible reference state.
        #
        # Use |+...+> so that the state is not generally an
        # eigenstate of the full Ising Hamiltonian.
        for q in range(self.num_qubits):
            qc.h(q)

        # Evolution time for this Krylov state.
        total_time = (
            krylov_index *
            self.evolution_step
        )

        if total_time > 0:

            dt = (
                total_time /
                self.trotter_steps
            )

            for _ in range(
                self.trotter_steps
            ):
                self._trotter_step(
                    qc,
                    dt,
                )

        qc.measure(
            range(self.num_qubits),
            range(self.num_qubits),
        )

        return qc

    def build_circuits(self):
        """
        Construct the complete batch of Krylov-state circuits.
        """

        return [
            self.build_krylov_circuit(k)
            for k in range(
                self.krylov_dimension
            )
        ]

    def build_circuit(self):
        """
        Compatibility helper.

        For QASP the natural object is a circuit batch, so this
        method returns the first member only. QMAP execution should
        preferentially use build_circuits().
        """

        return self.build_circuits()[0]

    def get_observables(self):
        """
        Return the Hamiltonian associated with the subspace problem.
        """

        return self.build_hamiltonian()

    def get_metadata(self) -> dict:
        """
        Metadata useful for QMAP timing/dataflow characterization.
        """

        return {
            "problem_name": self.name,
            "pattern": self.pattern,

            "num_qubits":
                self.num_qubits,

            "krylov_dimension":
                self.krylov_dimension,

            "trotter_steps":
                self.trotter_steps,

            "evolution_step":
                self.evolution_step,

            "shots":
                self.shots,

            "num_circuits":
                self.krylov_dimension,

            "locality_class":
                "batched",

            # One logical batch submission where supported.
            "expected_qpu_calls":
                1,

            # Classical analysis follows completion of the batch.
            "expected_classical_sync_points":
                1,

            "quantum_compute_region":
                "batched Krylov-state generation",

            "classical_role":
                "subspace assembly and reduced solve",

            "quantum_role":
                "Krylov-state generation and measurement",
        }


def get_problem(**kwargs):
    """
    Factory function for QMAP-style dynamic loading.
    """

    return QASPSKQD(**kwargs)
