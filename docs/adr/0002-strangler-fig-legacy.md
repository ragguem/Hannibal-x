# ADR 0002 — Migration progressive : ancien code dans `legacy/`, tests de caractérisation

- Statut : réalisé (`legacy/` supprimé le 2026-11-20)
- Date : 2026-11-18
- Lot : 0

## Contexte

L'application `app_v3` et l'assistant `hx2_service_c` fonctionnent et servent aux démonstrations.
Une réécriture d'un bloc ferait perdre des comportements non documentés (pilotage, capitaines, exercice, recommandations).

## Décision

- L'ancien code est déplacé tel quel dans `legacy/` ; il reste exécutable jusqu'au Lot 6 (`HANNIBAL_HOME` pour ses données).
- Avant de réécrire une fonction, son comportement est figé par des **goldens** (`eval/characterization/`) :
  entrées dans `cases/`, sorties de l'ancien code dans `golden/`.
- La nouvelle implémentation est vérifiée contre les mêmes goldens. Un écart voulu se décide dans le lot concerné
  et se lit dans le diff des goldens.
- Les comportements dépendants du temps (scénario à 2 Hz, doctrine) sont enregistrés sur le serveur
  (scripts de `eval/characterization/scripts/`), les enregistrements restent hors dépôt.
- `legacy/` n'est plus modifié, sauf correctif bloquant pour une démonstration.

## Conséquences

- La parité fonctionnelle (plan § 2) se mesure, elle ne se déclare pas.
- `legacy/` est supprimé au Lot 6, après la recette de parité.

## Réalisation (2026-11-20)

- Chaque module de l'ancien code a son équivalent dans `hannibal_core` ; la notation du jeu réel
  (`evaluate.check`) est devenue `hannibal_core.signals.score_interpretation`.
- Les goldens ne rejouent plus que `hannibal_core` : ils deviennent la référence figée. Les écarts voulus
  (`golden/core/`) ont remplacé les goldens d'origine et restent décrits dans `eval/characterization/README.md`.
- Les six scénarios vivent dans `apps/api/scenarios/` ; l'ancien code reste lisible dans l'historique git.
