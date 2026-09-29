# qtes_trotter_ising.py

from qiskit import QuantumCircuit
from qiskit.circuit import Parameter


class QTESTrotterIsing:
    """
    QTES diagnostic problem:
    Trotterized time evolution for a 1D transverse-field Ising model.

    Pattern: QTES
    Locality: High / contiguous
    Purpose: Measure timing and dataflow behavior for a quantum-resident
             Hamiltonian time-evolution region.
    """

    name = "qtes_trotter_ising"
    pattern = "QTES"

    def __init__(
        self,
        num_qubits: int = 6,
        trotter_steps: int = 3,
        j_coupling: float = 1.0,
        h_field: float = 0.7,
        time: float = 1.0,
        shots: int = 1024,
    ):
        self.num_qubits = num_qubits
        self.trotter_steps = trotter_steps
        self.j_coupling = j_coupling
        self.h_field = h_field
        self.time = time
        self.shots = shots

    def build_circuit(self) -> QuantumCircuit:
        """
        Build a first-order Trotter circuit for:

            H = -J sum_i Z_i Z_{i+1} - h sum_i X_i

        Evolution:

            U(t) ≈ [ exp(i J dt ZZ) exp(i h dt X) ]^r

        where dt = t / r.
        """

        n = self.num_qubits
        r = self.trotter_steps
        dt = self.time / r

        qc = QuantumCircuit(n, n)

        # Initial state: simple non-eigenstate for dynamics
        for q in range(n):
            qc.h(q)

        for _ in range(r):
            # ZZ interaction terms
            for q in range(n - 1):
                self._zz_evolution(qc, q, q + 1, self.j_coupling * dt)

            # Optional periodic boundary condition
            # self._zz_evolution(qc, n - 1, 0, self.j_coupling * dt)

            # Transverse X-field terms
            for q in range(n):
                qc.rx(2.0 * self.h_field * dt, q)

        qc.measure(range(n), range(n))
        return qc

    @staticmethod
    def _zz_evolution(qc: QuantumCircuit, q0: int, q1: int, theta: float):
        """
        Implements exp(i theta Z_q0 Z_q1), up to sign convention.

        Standard decomposition:
            CNOT q0 -> q1
            RZ(2 theta) on q1
            CNOT q0 -> q1
        """
        qc.cx(q0, q1)
        qc.rz(2.0 * theta, q1)
        qc.cx(q0, q1)

    def get_metadata(self) -> dict:
        """
        Metadata fields useful for QMAP timing/dataflow characterization.
        """
        return {
            "problem_name": self.name,
            "pattern": self.pattern,
            "num_qubits": self.num_qubits,
            "trotter_steps": self.trotter_steps,
            "shots": self.shots,
            "hamiltonian": "1D transverse-field Ising",
            "locality_class": "contiguous",
            "expected_classical_sync_points": 1,
            "expected_qpu_calls": 1,
            "quantum_compute_region": "state preparation + trotterized time evolution + measurement",
        }


def get_problem(**kwargs):
    """
    Factory function for QMAP-style dynamic loading.
    """
    return QTESTrotterIsing(**kwargs)
