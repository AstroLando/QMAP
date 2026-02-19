# src/tests/heavyTest.py
from src.problemRunner import ProblemRunner
from Problems.RNG import RNG
from Problems.QFT import QuantFT as QFT
from Problems.BV import BV
from Problems.Grovers import Grovers
from Problems.QPE import QPE


PR = ProblemRunner()

# These problems will run in this order with a large qubit range. 
# To ensure a reasonable time frame, the stepsize has been increased to 4
# Your backend needs at least 126 qubits for these problems to work.

PR.addProblem(RNG(), maxQubits=126, qubitStep=4)
PR.addProblem(QFT(), maxQubits=126, qubitStep=4)
PR.addProblem(BV(), maxQubits=126, qubitStep=4)
PR.addProblem(Grovers(), maxQubits=126, qubitStep=4)
PR.addProblem(QPE(), maxQubits=126, qubitStep=4)

# For BACKEND_NAME, insert either "garnet", "fakeGarnet", "mockGarnet", or "Sirius"
# For TOKEN, insert your resonance API token.

PR.runProblemSet(*PR.setUpIQM("BACKEND_NAME", "TOKEN"))