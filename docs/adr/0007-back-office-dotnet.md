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

## Complément du 2026-11-21 — Lot 7

Constat : à la fin du Lot 6, le back-office ne porte que les comptes, les rôles et les sessions. Scénarios, missions,
navires et lecture du registre sont restés dans `apps/api`, qui mélange gestion, exécution et IA.

Décision :

- Règle de partage : ce qui a besoin de `packages/core` ou d'un modèle pendant la mission reste en Python ; tout le
  reste appartient au back-office.
- Le back-office porte en plus : l'administration des utilisateurs, le catalogue des **classes de navires**
  (caractéristiques) et des **navires**, les **scénarios** (import et export YAML validés, versions, publication ;
  éditeur par formulaires plus tard), la **planification des missions** (participants, statuts) et
  l'**historique**. Schémas à lui : `identity`, `catalog`, `planning`. La lecture du registre reste dans
  `apps/api` tant qu'aucun rapport ne croise missions et comptes.
- Un seul écrivain par schéma ; le back-office ne lit d'`ops` que des vues versionnées (`ops_read`) ; le back-office
  appelle `apps/api`, jamais l'inverse, et le lancement est idempotent ; l'identifiant de mission naît dans le
  back-office ; le back-office est le seul à autoriser.
- Performance : aucune écriture en base par requête relayée (session en cache), aucun appel entre services pendant
  la mission. Le back-office, sans état, peut tourner en plusieurs instances ; il deviendra le répartiteur des
  missions entre moteurs à la 2.0.0.
- `apps/api` garde la mission en cours, les ordres, la voix, les décisions, l'écriture du registre, le débrief,
  la doctrine et le glossaire. `ops.missions` devient le déroulé d'une mission planifiée, sous le même identifiant.
- Au lancement, le back-office envoie à `apps/api` une photo figée (version du scénario et caractéristiques des
  navires) par un contrat interne ; `apps/api` ne lit plus de fichier de scénario ni de catalogue.

Conséquences : environ 7,5 semaines (Lot 7 du plan de réalisation) ; l'identifiant de mission est partagé entre les
deux services, couvert par des tests de contrat des deux côtés ; les goldens ne changent pas, les caractéristiques
par défaut des classes reprenant les limites actuelles.
