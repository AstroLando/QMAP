# src/qmap/main.py
import yaml
import os
from dotenv import load_dotenv

# Import the runner and individual problems
from .problemRunner import ProblemRunner
from .problems.RNG import RNG
from .problems.QPE import QPE
from .problems.QFT import QuantFT
from .problems.BV import BV
from .problems.Grovers import Grovers

# Mapping string names from config.yml to Class instances
PROBLEM_MAP = {
    "RNG": RNG,
    "QPE": QPE,
    "QFT": QuantFT,
    "BV": BV,
    "Grovers": Grovers
}

def load_config(path):
    """Loads the YAML configuration file."""
    with open(path, 'r') as file:
        return yaml.safe_load(file)

def main():
    # Find the directory where main.py actually lives
    internal_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Path to config.yml (same folder as main.py)
    config_path = os.path.join(internal_dir, "config.yml")
    config = load_config(config_path)
    
    # BASE_DIR is two levels up from main.py: src/qmap/ -> ria_QMAP/
    BASE_DIR = os.path.abspath(os.path.join(internal_dir, "..", ".."))
    
    # Path to tokens.env at project root
    env_path = os.path.join(BASE_DIR, config.get('env_path', 'tokens.env'))
    load_dotenv(env_path)

    runner = ProblemRunner()
    
    # 2. Select the setup method based on the host in config.yml
    host = config['host'].lower()
    backend_name = config['backend']
    
    print(f"Initializing {host} connection for backend: {backend_name}...")

    if host == 'ibm':
        backend, sampler, name, b_type = runner.setUpIBM(backend_name)
    elif host == 'iqm':
        backend, sampler, name, b_type = runner.setUpIQM(backend_name)
    elif host == 'quantinuum':
        backend, sampler, name, b_type = runner.setUpQuantinuum(backend_name)
    elif host == 'ionq':
        backend, sampler, name, b_type = runner.setUpIonQ(backend_name)
    elif host == 'iqm_onprem':
        backend, sampler, name, b_type = runner.setUpIQMOnPrem(backend_name)
    else:
        raise ValueError(f"Unknown host: {host}")

    # 3. Batch process problems defined in config.yml
    requested_problems = config.get('problems', [])
    
    for prob_cfg in requested_problems:
        prob_name = prob_cfg.get('name')
        
        if prob_name in PROBLEM_MAP:
            # Merge global defaults with problem-specific overrides
            # prob_cfg keys (like 'reps') will overwrite the global 'config' keys
            merged_cfg = {**config, **prob_cfg}
            
            # Remove the 'problems' list from the merged_cfg to avoid passing it to addProblem
            merged_cfg.pop('problems', None)
            
            runner.addProblem(
                problem=PROBLEM_MAP[prob_name](), 
                **merged_cfg
            )
            print(f"Added {prob_name} with configuration: {prob_cfg}")
        else:
            print(f"Warning: Problem '{prob_name}' not found in PROBLEM_MAP. Skipping.")

    # 4. Execute the experiment set
    runner.runProblemSet(backend, sampler, name, b_type)

if __name__ == "__main__":
    main()
