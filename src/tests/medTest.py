# src/tests/medTest.py
from src.problemRunner import ProblemRunner
from Problems.RNG import RNG
from Problems.QFT import QuantFT as QFT
from Problems.BV import BV
from Problems.Grovers import Grovers
from Problems.QPE import QPE


PR = ProblemRunner()

# These problems will run in this order with a medium qubit range.
# Your backend needs at least 20 qubits for these problems to work.

PR.addProblem(RNG(), maxQubits=20)
PR.addProblem(QFT(), maxQubits=20)
PR.addProblem(BV(), maxQubits=20)
PR.addProblem(Grovers(), maxQubits=20)
PR.addProblem(QPE(), maxQubits=20)

# For BACKEND_NAME, insert either "garnet", "fakeGarnet", "mockGarnet", or "Sirius"
# For TOKEN, insert your resonance API token.

PR.runProblemSet(*PR.setUpIQM("BACKEND_NAME", "TOKEN"))