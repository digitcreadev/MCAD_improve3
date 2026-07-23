from __future__ import annotations
import matplotlib.pyplot as plt
import numpy as np
from common import DATA, POLICY_LABELS, save

rows = DATA['core_foodmart']
policies = [POLICY_LABELS[r['policy']] for r in rows]
fa = [r['false_allow_rate'] for r in rows]
fb = [r['false_block_rate'] for r in rows]
f1 = [r['F1_block'] for r in rows]

x = np.arange(len(policies))
width = 0.25
fig, ax = plt.subplots(figsize=(10, 5.2))
ax.bar(x - width, fa, width, label='False allow')
ax.bar(x, fb, width, label='False block')
ax.bar(x + width, f1, width, label='F1 blocage')
ax.set_xticks(x)
ax.set_xticklabels(policies, rotation=10)
ax.set_ylim(0, 1.08)
ax.set_ylabel('Valeur normalisée')
ax.set_title('Performance de détection des requêtes non contributives (FoodMart)')
ax.legend(loc='upper right')
save(fig, 'fig_detection_performance.png')
