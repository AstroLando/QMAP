from problemRunner import ProblemRunner
from Problems.RNG import RNG
from Problems.QFT import QuantFT as QFT
from Problems.BV import BV
from Problems.Grovers import Grovers
from Problems.QPE import QPE


PR = ProblemRunner()

# These problems will run in this order with default repititions, shots, and qubit ranges. 

PR.addProblem(RNG())
PR.addProblem(QFT())
PR.addProblem(BV())
PR.addProblem(Grovers())
PR.addProblem(QPE())

# For BACKEND_NAME, insert either "garnet", "fakeGarnet", "mockGarnet", or "Sirius"
# For TOKEN, insert your resonance API token.



PR.runProblemSet(*PR.setUpIQM("BACKEND_NAME", "TOKEN"))