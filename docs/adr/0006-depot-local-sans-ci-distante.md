# ADR 0006 — Dépôt git local, contrôles sur le poste

- Statut : accepté
- Date : 2026-11-18
- Lot : 0

## Contexte

Tous les commits restent en local : pas de dépôt distant, donc pas de CI hébergée ni de demande de fusion.
Un seul développeur. Le serveur cible n'a pas Internet.

## Décision

- Les crochets **pre-commit** sont le contrôle de chaque commit : ruff, mypy, import-linter, pytest, validité
  YAML/TOML/JSON, refus des fichiers de données. Ils fonctionnent hors ligne (outils verrouillés dans `uv.lock`).
- **`tools/check.ps1`** (poste Windows) et **`tools/check.sh`** (serveur) rejouent toute la chaîne de la CI, avec un
  seuil de couverture à 85 %. Ils sont obligatoires avant chaque étiquette `vX.Y.Z` ; `-Image` / `--image` ajoute
  la construction de l'image API quand Docker est disponible.
- `.github/workflows/ci.yml` est conservé tel quel, inactif, pour le jour où un dépôt distant sera ajouté.
- Pas de contournement des crochets (`--no-verify`), sauf commit de travail explicitement repris avant l'étiquette.
- Sauvegarde : `tools/backup.ps1` crée un `git bundle` complet (historique et étiquettes) sur un support externe,
  au moins à chaque fin de lot.

## Conséquences

- La qualité ne dépend que de la discipline locale : un commit qui contourne les crochets n'est rattrapé
  qu'au `tools/check` de fin de lot.
- Le dépôt n'existe qu'en un exemplaire tant qu'aucune sauvegarde n'est faite.
- Ajouter un dépôt distant plus tard ne demande aucun changement : la CI est déjà écrite.
