from problemRunner import ProblemRunner
from Problems.RNG import RNG
from Problems.QFT import QuantFT as QFT
from Problems.BV import BV
from Problems.Grovers import Grovers
from Problems.QPE import QPE


PR = ProblemRunner()

PR.addProblem(RNG())
PR.addProblem(QFT())
PR.addProblem(QFT())
PR.addProblem(Grovers())
PR.addProblem(QPE())

b, s, n = PR.setUpIQM("mockGarnet", "INSERT TOKEN")

PR.runProblemSet(b, s, n)