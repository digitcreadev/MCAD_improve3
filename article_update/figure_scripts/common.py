from __future__ import annotations
import json
from pathlib import Path
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parent
DATA_PATH = BASE / 'article_eval_data.json'
OUT_DIR = BASE.parent / 'article_figures'
OUT_DIR.mkdir(parents=True, exist_ok=True)

with DATA_PATH.open('r', encoding='utf-8') as f:
    DATA = json.load(f)

POLICY_LABELS = {
    'mcad_gate': 'MCAD-Gate',
    'measure_overlap': 'Measure overlap',
    'naive': 'Naïve',
    'random_matched': 'Random matched',
}


def save(fig, filename: str):
    path = OUT_DIR / filename
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches='tight')
    plt.close(fig)
    print(path)
    return path
