# src/tests/heavyTest.py
from qmap.problemRunner import ProblemRunner
from qmap.problems.RNG import RNG
from qmap.problems.QFT import QuantFT as QFT
from qmap.problems.BV import BV
from qmap.problems.Grovers import Grovers
from qmap.problems.QPE import QPE


PR = ProblemRunner()

# These qmap.problems will run in this order with a large qubit range. 
# To ensure a reasonable time frame, the stepsize has been increased to 4
# Your backend needs at least 126 qubits for these qmap.problems to work.

PR.addProblem(RNG(), maxQubits=126, qubitStep=4)
PR.addProblem(QFT(), maxQubits=126, qubitStep=4)
PR.addProblem(BV(), maxQubits=126, qubitStep=4)
PR.addProblem(Grovers(), maxQubits=126, qubitStep=4)
PR.addProblem(QPE(), maxQubits=126, qubitStep=4)

# For BACKEND_NAME, insert either "garnet", "fakeGarnet", "mockGarnet", or "Sirius"
# For TOKEN, insert your resonance API token.

PR.runqmap.problemset(*PR.setUpIQM("BACKEND_NAME", "TOKEN"))