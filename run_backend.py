import os
import sys
import subprocess

# Set PYTHONPATH to include project root
project_root = os.path.dirname(os.path.abspath(__file__))
os.environ['PYTHONPATH'] = project_root + os.pathsep + os.environ.get('PYTHONPATH', '')

# Run the backend
subprocess.run([sys.executable, os.path.join('python-backend', 'main.py')])
