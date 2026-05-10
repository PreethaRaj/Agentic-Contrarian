"""
CHANGELOG (new file):
- Launcher script to run Streamlit from project root so 'app' package resolves.
- Usage: python run_dashboard.py   (or see README)
- Internally calls: streamlit run app/ui/dashboard.py with PYTHONPATH set.
"""

import subprocess
import sys
import os

# Ensure project root is on PYTHONPATH before Streamlit forks its process
env = os.environ.copy()
project_root = os.path.dirname(os.path.abspath(__file__))
existing = env.get("PYTHONPATH", "")
env["PYTHONPATH"] = f"{project_root}{os.pathsep}{existing}" if existing else project_root

cmd = [sys.executable, "-m", "streamlit", "run", "app/ui/dashboard.py"] + sys.argv[1:]
print(f"[launcher] PYTHONPATH={env['PYTHONPATH']}")
print(f"[launcher] Running: {' '.join(cmd)}")
subprocess.run(cmd, env=env)
