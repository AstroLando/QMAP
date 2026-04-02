# src/tests/medTest.py
from qmap.problemRunner import ProblemRunner
from qmap.problems.RNG import RNG
from qmap.problems.QFT import QuantFT as QFT
from qmap.problems.BV import BV
from qmap.problems.Grovers import Grovers
from qmap.problems.QPE import QPE


PR = ProblemRunner()

# These qmap.problems will run in this order with a medium qubit range.
# Your backend needs at least 20 qubits for these qmap.problems to work.

PR.addProblem(RNG(), maxQubits=20)
PR.addProblem(QFT(), maxQubits=20)
PR.addProblem(BV(), maxQubits=20)
PR.addProblem(Grovers(), maxQubits=20)
PR.addProblem(QPE(), maxQubits=20)

# For BACKEND_NAME, insert either "garnet", "fakeGarnet", "mockGarnet", or "Sirius"
# For TOKEN, insert your resonance API token.

PR.runqmap.problemset(*PR.setUpIQM("BACKEND_NAME", "TOKEN"))