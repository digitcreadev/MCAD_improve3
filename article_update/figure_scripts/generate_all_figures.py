from __future__ import annotations
import subprocess
from pathlib import Path

base = Path(__file__).resolve().parent
scripts = [
    'generate_protocol_figure.py',
    'generate_detection_performance.py',
    'generate_efficiency_explainability.py',
    'generate_comparative_analysis.py',
    'generate_backend_portability.py',
]
for s in scripts:
    subprocess.run(['python', str(base / s)], check=True)
print('All article figures generated.')
