# ADR 0001 — Monodépôt, espaces de travail uv et pnpm

- Statut : accepté
- Date : 2026-11-18
- Lot : 0

## Contexte

Le code actuel est réparti en dossiers copiés (`app`, `app_v2`, `app_v3`, `hx`, `v2`) sans dépendances déclarées.
La cible 1.1.0 compte plusieurs processus Python (api, asr, doctrine, sim-bridge), un front React et des contrats partagés.
Un seul développeur porte le MVP.

## Décision

- Un seul dépôt. Python dans un espace de travail **uv** (`packages/*`, `apps/*`), front dans un espace **pnpm**.
- Python 3.12 partout, imposé par `rclpy` de ROS 2 Jazzy dans `sim-bridge`.
- Un seul verrou par écosystème (`uv.lock`, `pnpm-lock.yaml`), installé en mode figé en CI.
- Le code commun vit dans des paquets (`hannibal-platform`, `hannibal-contracts`), jamais copié.
- Les règles de couches sont vérifiées par import-linter dans la CI.

## Conséquences

- Un changement de contrat et ses consommateurs passent dans le même commit.
- Une seule CI, un seul outillage de qualité (ruff, mypy strict, pytest).
- Les images Docker se construisent depuis la racine du dépôt.
