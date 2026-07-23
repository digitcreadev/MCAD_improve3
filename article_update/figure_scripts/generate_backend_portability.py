from __future__ import annotations
import matplotlib.pyplot as plt
import numpy as np
from common import DATA, save

rows = DATA['backend_portability']
labels = [f"{r['dataset']}\n{r['backend']}" for r in rows]
contract = [r['contract_success_rate'] for r in rows]
latency = [r['decision_latency_p95_ms'] / 0.25 for r in rows]

x = np.arange(len(labels))
width = 0.34
fig, ax = plt.subplots(figsize=(10.5, 5.2))
ax.bar(x - width/2, contract, width, label='Succès du contrat ALLOW/BLOCK')
ax.bar(x + width/2, latency, width, label='Latence p95 (normalisée)')
ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=10)
ax.set_ylim(0, 1.08)
ax.set_ylabel('Valeur / normalisation')
ax.set_title('Portabilité backend et évaluation technique')
ax.legend(loc='upper right')
ax.text(0.5, 0.96, '480 validations : 2 datasets × 2 backends × 4 scénarios × 30 répétitions',
        transform=ax.transAxes, ha='center', va='top', fontsize=10,
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))
save(fig, 'fig_backend_portability.png')
