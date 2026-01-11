from src.qmap import ProblemRunner
from src.qmap.problems import RNG, QFT, BV, QPE, Grovers
from dotenv import load_dotenv
import os, yaml

# Retrieve API tokens and experiment configurations from config.yml
# config = utils.load_config("config.yml")
with open(f"{os.getcwd()}/config.yml", 'r') as file:
    config = yaml.safe_load(file)
load_dotenv(dotenv_path="tokens.env")
HOST, BACKEND = config['host'], config['backend']

# These problems will run in this order with default repetitions, shots, and qubit ranges. 
# Your backend needs at least 8 qubits for these problems to work.
minQubits, maxQubits = config['minQubits'], config['maxQubits']
minShots, maxShots = config['minShots'], config['maxShots']
qubitStep, shotStep, reps = config['qubitStep'], config['shotStep'], config['reps']

print("Adding problems...")
PR = ProblemRunner()
PR.addProblem(RNG.RNG(), reps, minQubits, maxQubits, qubitStep, minShots, maxShots, shotStep)
PR.addProblem(QFT.QuantFT(), reps, minQubits, maxQubits, qubitStep, minShots, maxShots, shotStep)
PR.addProblem(BV.BV(), reps, minQubits, maxQubits, qubitStep, minShots, maxShots, shotStep)
PR.addProblem(Grovers.Grovers(), reps, minQubits, maxQubits, qubitStep, minShots, maxShots, shotStep)
PR.addProblem(QPE.QPE(), reps, minQubits, maxQubits, qubitStep, minShots, maxShots, shotStep)

if "iqm" in HOST:
    # print("Running problem set...")
    # token = os.getenv('IQM_TOKEN')
    print(f"===> Backend chosen: {BACKEND}")
    PR.runProblemSet(*PR.setUpIQM(BACKEND))
elif "ibm" in HOST:
    # token = os.getenv('IBM_TOKEN')
    # instance = os.getenv('IBM_INSTANCE')
    print(f"===> Backend chosen: {BACKEND}")
    PR.runProblemSet(*PR.setUpIBM(BACKEND))
elif "quantinuum" in HOST:
    print(f"===> Backend chosen: {BACKEND}")
    PR.runProblemSet(*PR.setUpQuantinuum(BACKEND))
