from __future__ import annotations
import matplotlib.pyplot as plt
import numpy as np
from common import DATA, POLICY_LABELS, save

rows = DATA['core_foodmart']
policies = [POLICY_LABELS[r['policy']] for r in rows]
exec_rate = [r['non_contributive_execution_rate'] for r in rows]
explain = [r['explanation_coverage_rate'] for r in rows]
latency = [r['decision_latency_p95_ms'] / 0.25 for r in rows]  # normalized near 1 for MCAD

x = np.arange(len(policies))
width = 0.25
fig, ax = plt.subplots(figsize=(10, 5.2))
ax.bar(x - width, exec_rate, width, label='Exec. non contributives')
ax.bar(x, explain, width, label='Couverture des explications')
ax.bar(x + width, latency, width, label='Latence p95 (normalisée)')
ax.set_xticks(x)
ax.set_xticklabels(policies, rotation=10)
ax.set_ylim(0, 1.08)
ax.set_ylabel('Valeur / normalisation')
ax.set_title('Efficacité opérationnelle et explicabilité (FoodMart)')
ax.legend(loc='upper right')
save(fig, 'fig_efficiency_explainability.png')
