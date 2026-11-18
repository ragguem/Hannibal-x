# ADR 0007 — Back-office métier en .NET 10, cœur tactique et IA en Python

- Statut : accepté
- Date : 2026-11-18
- Lot : 1

## Contexte

La 1.1.0 prévoit un seul langage serveur (Python 3.12). Le domaine se partage pourtant en deux :

- le **cœur tactique** (signaux, ordres, cinématique, flotte à 2 Hz, scénarios) et l'**IA** (voix, doctrine, LLM),
  repris de l'ancien code Python, appelés en continu par le guide et prouvés par les goldens ;
- le **back-office** (comptes, rôles, sessions, catalogue de scénarios, registre, intégration avec d'autres
  systèmes), sans code existant, fait de règles de gestion classiques, où .NET (Identity, autorisations par
  politique, EF Core, typage fort) est plus complet et mieux maîtrisé par le développeur.

## Décision

- **`apps/backoffice`** : ASP.NET Core sur **.NET 10 LTS** (support jusqu'en novembre 2028), architecture hexagonale
  (`Domain`, `Application`, `Infrastructure`, `Api`), règles de couches vérifiées par test.
  - Il est le **point d'entrée unique** du front : authentification (comptes locaux, Argon2id, cookie de session),
    RBAC, puis relais YARP vers `apps/api` avec le jeton interne et l'identité de l'utilisateur.
  - Il porte : comptes et rôles, catalogue de scénarios (validation du schéma YAML `schema_version: 1`),
    lecture paginée du registre, et à partir de la 1.2.0 le relais `integration_outbox` vers NATS et les webhooks.
  - Schémas PostgreSQL à lui : `identity`, `catalog`. Il lit `audit` avec un rôle SQL en lecture seule.
- **Python** garde `packages/core`, `apps/api` (mission en cours, ordres, guide, flux SSE, écriture du registre)
  et les services IA et `sim-bridge`. Il ne gère plus de comptes.
- Les deux côtés ne se parlent que par les contrats : OpenAPI 3.1, JSON Schema dans `packages/contracts`,
  AsyncAPI pour les événements. Le contrat d'abord (ADR 0005) s'applique au code C# comme au code Python.
- Socle .NET équivalent à `packages/platform` : journal JSON avec `request_id`, `/health`, `/metrics` Prometheus,
  jeton interne, traducteur d'erreurs au format `ErrorBody`.
- Outillage local (ADR 0006) : `global.json`, gestion centralisée des paquets, `Nullable` et avertissements
  bloquants ; `dotnet format`, `dotnet build` et `dotnet test` ajoutés aux crochets pre-commit et à `tools/check`.

## Conséquences

- Deux chaînes d'outils pour un développeur seul : environ une semaine de plus au Lot 1 pour le socle .NET.
- L'authentification et le RBAC passent du Lot 2 Python à `apps/backoffice`.
- Un saut réseau de plus entre le front et `apps/api` (YARP, en mémoire sur la même machine, SSE compris).
- Un système tiers .NET, Java ou autre s'intègre par les mêmes contrats, sans dépendre du langage d'un service.
