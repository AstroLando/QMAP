# qsmc_sampling.py

import numpy as np

from qiskit import QuantumCircuit
from qiskit.circuit import ParameterVector


class QSMCSampling:
    """
    QSMC diagnostic problem:
    Repeated quantum sampling from a parameterized correlated state.

    Pattern: QSMC
    Locality: Moderate / batched

    Purpose:
        Represent a hybrid sampling workflow in which the QPU
        generates many samples from a quantum distribution before
        returning results to the classical side for aggregation
        and statistical analysis.

    This is intentionally a generic sampling diagnostic rather than
    an implementation of one specific scientific Monte Carlo method.
    """

    name = "qsmc_sampling"
    pattern = "QSMC"

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

        # One parameter per qubit per layer
        self.theta = ParameterVector(
            "theta",
            length=num_qubits * layers
        )

        if parameters is None:
            # Deterministic defaults for reproducible QMAP runs
            self.parameters = np.linspace(
                0.2,
                1.0,
                len(self.theta)
            )
        else:
            if len(parameters) != len(self.theta):
                raise ValueError(
                    f"Expected {len(self.theta)} parameters, "
                    f"received {len(parameters)}."
                )

            self.parameters = np.asarray(
                parameters,
                dtype=float
            )

    def build_sampling_circuit(self) -> QuantumCircuit:
        """
        Construct a parameterized circuit that generates a correlated
        probability distribution.

        Each layer contains:

            Ry rotations
            nearest-neighbor CX entanglement

        The circuit terminates in computational-basis measurement,
        producing bitstrings that act as Monte Carlo samples.
        """

        qc = QuantumCircuit(
            self.num_qubits,
            self.num_qubits
        )

        p = 0

        for _ in range(self.layers):

            # Parameterized local rotations
            for q in range(self.num_qubits):
                qc.ry(
                    self.theta[p],
                    q
                )
                p += 1

            # Nearest-neighbor correlations
            for q in range(self.num_qubits - 1):
                qc.cx(q, q + 1)

        # Measurement produces the samples
        qc.measure(
            range(self.num_qubits),
            range(self.num_qubits)
        )

        return qc

    def build_circuit(self) -> QuantumCircuit:
        """
        Return the parameter-bound sampling circuit.
        """

        qc = self.build_sampling_circuit()

        bindings = {
            self.theta[i]: self.parameters[i]
            for i in range(len(self.theta))
        }

        return qc.assign_parameters(bindings)

    def get_metadata(self) -> dict:
        """
        Metadata useful for QMAP timing and dataflow characterization.
        """

        return {
            "problem_name": self.name,
            "pattern": self.pattern,

            "num_qubits": self.num_qubits,
            "layers": self.layers,
            "shots": self.shots,
            "num_parameters": len(self.theta),

            "locality_class": "batched",

            # One logical submission can generate many samples.
            "expected_qpu_calls": 1,

            # Classical processing occurs after the sample batch returns.
            "expected_classical_sync_points": 1,

            "samples_per_qpu_call": self.shots,

            "quantum_compute_region":
                "state preparation + repeated quantum sampling",

            "classical_role":
                "sample aggregation and statistical analysis",

            "quantum_role":
                "generation of samples from correlated distribution",
        }


def get_problem(**kwargs):
    """
    Factory function for QMAP-style dynamic loading.
    """
    return QSMCSampling(**kwargs)
