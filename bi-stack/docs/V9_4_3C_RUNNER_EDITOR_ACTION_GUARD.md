# V9.4.3c — Runner Editor Action Guard

## Objectif

Corriger l’accessibilité des boutons situés sous `SELECTED QUERY EDITOR` dans le Scenario Runner.

Les boutons suivants restent désactivés tant que l’éditeur ne contient aucune requête :

- `Evaluate`
- `Run`
- `Add to scenario`

## Correction

La fonction `updateEditorExecutionButtons()` active ces trois boutons uniquement si :

1. une session MCAD est active ;
2. le champ `runnerQueryText` contient un texte non vide.

La correction est rappelée après :

- changement de session ;
- chargement/suppression de scénario ;
- sélection d’une requête ;
- saisie manuelle dans l’éditeur ;
- rendu global de l’UI.

## Résultat attendu

À l’ouverture d’une session sans requête sélectionnée, `SELECTED QUERY EDITOR` est vide et les trois boutons sont désactivés.

Dès qu’une requête est sélectionnée ou saisie, les trois boutons deviennent utilisables.

Si l’éditeur redevient vide, les trois boutons redeviennent désactivés.
