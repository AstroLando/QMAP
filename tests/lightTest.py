from src.problemRunner import ProblemRunner
from Problems.RNG import RNG
from Problems.QFT import QuantFT as QFT
from Problems.BV import BV
from Problems.Grovers import Grovers
from Problems.QPE import QPE
from dotenv import load_dotenv
import os, yaml

# Retrieve API tokens and experiment configurations
# config = utils.load_config("config.yml")
with open("config.yml", 'r') as file:
    config = yaml.safe_load(file)
load_dotenv(dotenv_path=config['env_path'])
HOST = config['host']
BACKEND = config['backend']


# These problems will run in this order with default repititions, shots, and qubit ranges. 
# Your backend needs at least 8 qubits for these problems to work.
PR = ProblemRunner()

reps = config['reps']
minQubits = config['minQubits']
maxQubits = config['maxQubits']
qubitStep = config['qubitStep']
minShots = config['minShots']
maxShots = config['maxShots']
shotStep = config['shotStep']

print("Adding problems...")
# PR.addProblem(RNG(), reps, minQubits, maxQubits, qubitStep, minShots, maxShots, shotStep)
# PR.addProblem(QFT(), reps, minQubits, maxQubits, qubitStep, minShots, maxShots, shotStep)
# PR.addProblem(BV(), reps, minQubits, maxQubits, qubitStep, minShots, maxShots, shotStep)
PR.addProblem(Grovers(), reps, minQubits, maxQubits, qubitStep, minShots, maxShots, shotStep)
# PR.addProblem(QPE(), reps, minQubits, maxQubits, qubitStep, minShots, maxShots, shotStep)

if "iqm" in HOST:
    print("Running problem set...")
    token = os.getenv('IQM_TOKEN')
    PR.runProblemSet(*PR.setUpIQM(BACKEND, token=token))
elif "ibm" in HOST:
    token = os.getenv('IBM_TOKEN')
    instance = os.getenv('IBM_INSTANCE')
    PR.runProblemSet(*PR.setUpIBM(BACKEND, token=token, instance=instance))
