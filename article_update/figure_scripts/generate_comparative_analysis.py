from __future__ import annotations
import matplotlib.pyplot as plt
import numpy as np
from common import DATA, save

rows = DATA['paired_stats']
labels = [f"{r['campaign']}\nvs {r['baseline']}" for r in rows]
coverage = [r['coverage_preservation_ratio_mean'] for r in rows]
exec_red = [r['execution_reduction_ratio_mean'] for r in rows]
fa_red = [r['false_allow_reduction_ratio_mean'] for r in rows]

x = np.arange(len(labels))
width = 0.25
fig, ax = plt.subplots(figsize=(12, 5.6))
ax.bar(x - width, coverage, width, label='Préservation de couverture')
ax.bar(x, exec_red, width, label='Réduction des exécutions')
ax.bar(x + width, fa_red, width, label='Réduction des false allows')
ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=18, ha='right')
ax.set_ylim(0, 1.08)
ax.set_ylabel('Ratio moyen')
ax.set_title('Analyse comparative appariée des performances de MCAD-Gate')
ax.legend(loc='upper right')
save(fig, 'fig_paired_comparative_analysis.png')
