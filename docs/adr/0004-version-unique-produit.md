# ADR 0004 — Une version de produit, des contrats versionnés à part

- Statut : accepté
- Date : 2026-11-18
- Lot : 0

## Contexte

Le système est livré d'un bloc sur un serveur embarqué, sans Internet. Les autres systèmes qui s'y brancheront
dépendent des contrats, pas du code interne.

## Décision

- Version du produit en SemVer dans `VERSION`, reprise par tous les paquets et images.
  Lot N livré = `0.N.0` ; MVP de démonstration = `1.0.0`. Étiquette git `vX.Y.Z` à chaque livraison.
- Les contrats ont leur propre version (`CONTRACTS_VERSION`, versions OpenAPI et AsyncAPI, types d'événements
  `hx.<domaine>.<fait>.v1`). Un changement incompatible crée une nouvelle version majeure du contrat,
  l'ancienne est servie en parallèle le temps de la migration.
- Les routes HTTP publiques sont préfixées `/v1`.
- Messages de commit en Conventional Commits ; `CHANGELOG.md` tenu à chaque lot.

## Conséquences

- Une seule question pour l'exploitation : « quelle version tourne à bord ? ».
- Un client externe sait, par la version du contrat, s'il reste compatible.
