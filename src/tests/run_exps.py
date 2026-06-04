# src/tests/run_exps.py
import os, yaml
from dotenv import load_dotenv
from qmap.problemRunner import ProblemRunner
from qmap.problems import RNG, QFT, BV, QPE, Grovers

# Map string names from the YAML to the actual class constructors
PROBLEM_MAP = {
    "RNG": RNG.RNG,
    "QPE": QPE.QPE,
    "QFT": QFT.QuantFT,
    "BV": BV.BV,
    "Grovers": Grovers.Grovers
}

# 1. Retrieve configurations
config_path = os.path.join(os.getcwd(), "config.yml")
with open(config_path, 'r') as file:
    config = yaml.safe_load(file)

load_dotenv(dotenv_path="tokens.env")
HOST = config['host'].lower()
BACKEND = config['backend']

PR = ProblemRunner()
print("Parsing config and adding problems...")

# 2. Dynamically load problems based on config.yml
requested_problems = config.get('problems', [])

for prob_cfg in requested_problems:
    prob_name = prob_cfg.get('name')
    
    if prob_name in PROBLEM_MAP:
        # Merge global defaults with problem-specific overrides
        merged_cfg = {**config, **prob_cfg}
        
        # Drop the 'problems' array so it doesn't get passed as a kwarg
        merged_cfg.pop('problems', None)
        
        # **merged_cfg unpacks the dict directly into your addProblem kwargs
        PR.addProblem(
            problem=PROBLEM_MAP[prob_name](), 
            **merged_cfg
        )
        print(f"  -> Added {prob_name} to queue.")
    else:
        print(f"  -> WARNING: Problem '{prob_name}' not found in PROBLEM_MAP. Skipping.")

# 3. Execution Routing
print(f"\n===> Host: {HOST} | Backend: {BACKEND}")

host = HOST.lower()

if host == "iqm_onprem":
    PR.runProblemSet(*PR.setUpIQMOnPrem(BACKEND))

elif host == "iqm":
    PR.runProblemSet(*PR.setUpIQM(BACKEND))

elif "ibm" in host:
    PR.runProblemSet(*PR.setUpIBM(BACKEND))

elif "quantinuum" in host:
    PR.runProblemSet(*PR.setUpQuantinuum(BACKEND))

elif "ionq" in host:
    PR.runProblemSet(*PR.setUpIonQ(BACKEND))

else:
    print(f"Unknown host configuration: {HOST}")
