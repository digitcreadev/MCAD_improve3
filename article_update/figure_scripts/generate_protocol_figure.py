from __future__ import annotations
import matplotlib.pyplot as plt
from common import DATA, save

counts = DATA['campaign_counts']
labels = ['FoodMart core\n(3000 sessions)', 'Multi-dataset\n(1200 sessions)', 'Backend portability\n(480 validations)']
values = [counts['FoodMart core evaluation'], counts['Multi-dataset generalization'], counts['Backend portability']]
fig, ax = plt.subplots(figsize=(9, 5.2))
ax.bar(labels, values)
ax.set_ylabel('Nombre de sessions / validations')
ax.set_title('Protocole expérimental adopté')
for i, v in enumerate(values):
    ax.text(i, v + 40, str(v), ha='center', va='bottom', fontsize=10)
text = (
    'Mesures principales : false allow, false block, précision/rappel/F1 du blocage,\n'
    'taux d’exécutions non contributives, couverture explicative et latence p95.\n'
    'Total : 4680 sessions/validations et 37440 décisions au niveau requête.'
)
ax.text(0.5, 0.95, text, transform=ax.transAxes, ha='center', va='top', fontsize=10,
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))
ax.set_ylim(0, 3400)
save(fig, 'fig_protocol_adopte.png')
