# Journal des versions

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Versions : [SemVer](https://semver.org/lang/fr/),
un lot livré = `0.N.0`, MVP de démonstration = `1.0.0` (ADR 0004).

## [Non publié]

### Ajouté

- Contrat HTTP public 1.0.0 (`apps/api/openapi.json`, contrats `hannibal_contracts.missions`) : scénarios, missions,
  ordres directs, simulation d'un ordre, recommandations, barre manuelle, classification, réponse aux demandes,
  pilote automatique. Test de dérive : `uv run hx-export-openapi`.
- `apps/api` : handlers de mission sur le moteur `core.scenario`, `MissionRunner` à 2 Hz, catalogue YAML validé au
  démarrage, simulateur en mémoire (mode `fake`) ; une mission se joue de bout en bout sans écran. En mode `real`,
  une mission échoue en `dependency_unavailable` tant que le client `sim-bridge` n'est pas livré.
- Schéma `ops` 1.0.0 (Alembic, `uv run hx-api-migrate`) : `missions`, registre `audit_events` chaîné par SHA-256
  (trigger, append-only, `ops.verify_audit_chain`), boîte d'envoi `integration_outbox` (enveloppe CloudEvents).
  Une mission restée `running` au redémarrage de l'API passe en `interrupted` et l'événement est audité.
- Routes `GET /v1/audit` (pagination par `after_seq`) et `GET /v1/audit/integrity` ; auteur des actions lu dans
  l'en-tête `X-Hx-User` ; flux SSE `GET /v1/missions/{id}/events` (`situation`, puis `phase` en fin de mission).
- Compose : service `migrate` exécuté avant l'API ; port hôte PostgreSQL réglable par `HX_DEV_DB_PORT`
  (5432 est souvent pris par un PostgreSQL local).
- Revue des ordres : `POST /v1/missions/{id}/orders` en mode `review` (`awaiting_review`, `parent_id`),
  `GET /v1/commands/{id}`, `POST /v1/commands/{id}/decision` (`approve`, `reject`, `retry`, réponse `202`).
- Envoi fiable (migration `0002_ops_commands`) : `ops.commands`, `ops.command_dispatches`, répartiteur en tâche
  de fond (un envoi à la fois, attente croissante, 5 tentatives, validité de 30 s), réconciliation des envois
  restés `in_flight` au redémarrage. L'ordre n'est appliqué au moteur qu'une fois accepté par le simulateur ;
  en mode `real`, l'envoi échoue en transitoire tant que le client `sim-bridge` n'est pas livré.
- `apps/backoffice` : schéma `identity` (EF Core, migration `IdentityInitial`) : rôles et permissions, rôles de
  jeu (guide, escorte), comptes, sessions ; mots de passe en Argon2id (format PHC). Seeders `IDataSeeder`
  exécutés par `DataSeederOrchestrator` (ordre, transaction par seeder, UPSERT par clé métier, échecs agrégés en
  fin de chaîne) : `RoleSeeder`, `GameRoleSeeder`, `InitialAdminSeeder` (créé si absent, jamais modifié ;
  mot de passe par `HX_BACKOFFICE_INITIAL_ADMIN_PASSWORD`). Mode `migratedb` et service compose
  `backoffice-migrate` ; le serveur ne migre pas au démarrage.
- `apps/backoffice` : session par cookie `hx_session` (`POST`/`GET`/`DELETE /v1/session`, contrats `SignIn` et
  `SessionView`) ; jeton aléatoire stocké haché (SHA-256), expiration glissante 30 min et absolue 12 h. Une
  politique d'autorisation par permission ; relais YARP vers `apps/api` par route et permission, qui retire
  cookies et en-têtes `X-Hx-User`/`X-Internal-Token` entrants puis pose l'identité de session et le jeton interne.
- `services/sim_bridge` : pont vers LOTUSim (`POST`/`DELETE /ships`, `PUT /waypoints` pour toute la flotte en un
  appel par pas, `GET /state`), registre idempotent des manœuvres (`POST /maneuvers`, `GET /maneuvers/{id}`,
  journal JSON Lines relu au démarrage) ; couche anti-corruption ROS 2 (`MASCmdArray`, `VesselPositionArray`,
  `SetWaypoints`, lacet LOTUSim → cap vrai) et monde cinématique sans ROS pour le poste. Contrats internes
  `SpawnFleet`, `SteerFleet`, `WorldState`, `RecordManeuver`, `ManeuverRecord`. Image `kinematic` et `ros`
  (Jazzy, `lotusim_msgs` compilé depuis `interfaces/`), service compose `sim-bridge`.
- `apps/api` : client `SimBridgeClient` (simulateur et `FleetPort`) en mode `real`, sonde `sim-bridge` requise ;
  modèle cinématique partagé dans `hannibal_core.fleet.vessel_model`.
- `apps/web` (Lot 3) : console React 19 sur ports (`ApiPort`, `StreamPort`), client OpenAPI généré, TanStack Query
  (401 → retour à la connexion, pas de nouvel essai sur les 4xx), flux SSE avec relecture toutes les 2 s quand il
  tombe. Pages Connexion, Préparation, Console (radar, contacts, radio et synthèse vocale, objectifs, navires, ordre,
  simulation, validation, recommandations, demandes des commandants, mode automatique, barre manuelle, débrief) et
  Vue 3D (moteur three.js repris, mode démo). Faux back-office MSW (`dev:mock`), tests Vitest et Playwright ;
  contrôles web dans `tools/check` et pre-commit.
- `services/asr` (Lot 4) : `POST /transcribe` (WAV brut, noms des navires en paramètres), `WhisperEngine`
  (faster-whisper, `large-v3-turbo` puis `small` sur le même matériel, puis `small` sur processeur), vocabulaire
  du domaine en invite, une transcription à la fois ; `ScriptedSpeechEngine` pour le poste et les tests. Image
  `cpu` et image `gpu` (CUDA 12, cuDNN 9) ; modèles dans un volume, jamais dans l'image.
- `apps/api` : `POST /v1/missions/{id}/voice` (`VoiceOrders`) : l'audio est conservé, transcrit, puis suit le même
  chemin qu'un ordre clavier ; l'identifiant de l'enregistrement est celui de la commande (`source: voice`).
  Une parole non reconnue reste au registre (`transcribed` avec `refusal_reason`) avec son audio. Correction
  chaînée par `parent_id`. `GET /v1/audit/{command_id}/audio` ; erreurs métier `422` (`Unprocessable`).
  Sonde `asr` (optionnelle tant qu'aucune URL n'est fixée). Relais back-office `voice` (`command:submit`).
- `apps/web` : `VoiceCapture` (maintenir le bouton ou la barre d'espace hors des champs, import WAV, encodage
  WAV 16 kHz mono dans le navigateur), `InterpretationCard` (mots douteux surlignés sous 60 % de confiance,
  correction au clavier chaînée), page Registre (`audit:read`) : lignes regroupées par commande, audio, signal,
  décision, historique, filtres, pagination, état de la chaîne.
- Compose : service `asr` (moteur scripté par défaut, `HX_ASR_ENGINE=whisper` pour Whisper) et volume des
  enregistrements de l'API.
- `services/rerank` (Lot 5) : `POST /rerank` (1 à 3 formulations, 60 passages au plus), meilleur score par passage ;
  cross-encoder (`bge-reranker-v2-m3` ou modèle affiné) en demi-précision par lots de 16, ou score lexical sans
  modèle. Images `cpu` et `gpu`.
- `services/doctrine` (Lot 5) : `POST /ask`, `GET /glossary`, `GET /publications`, `POST /explain`. Pipeline repris
  de `hx2_service_c.py` : reformulation anglaise, recherche dense sur les deux formulations, questions générées et
  lignes de tableaux en option, reclassement, seuil de couverture, rédaction citée, contrôle d'ancrage, vérification
  par le modèle, second essai sur les meilleurs extraits, modèle de repli, style `quotes`, termes inconnus et
  propositions. Seuils, modèle et version d'index renvoyés dans chaque réponse. Lecture seule sur `v2` (rôle
  `hannibal_doctrine`, `sql/roles.sql`), `v2.index_versions` (`sql/index_versions.sql`) ; aucun mot de passe par
  défaut. Mode `sample` : corpus inventé et modèle scripté.
- `apps/api` : `POST /v1/doctrine/questions`, `GET /v1/doctrine/publications`, `GET /v1/glossary`,
  `POST /v1/commands/{id}/explanation`. Publications classifiées (`HX_DOCTRINE_CLASSIFIED_PUBLICATIONS`, ATP-28 par
  défaut) seulement avec `doctrine:classified` ; file GPU (1 en cours, 2 en attente, 20 s) puis `429 doctrine_busy` ;
  migration `0003_ops_doctrine_traces` ; audit `doctrine_answered` / `doctrine_refused`. Sonde `doctrine`.
- `apps/backoffice` : permissions `doctrine:ask`, `glossary:read` (tous les rôles), `doctrine:classified`
  (superviseur, administrateur) ; relais `doctrine`, `glossary`, `command-explanation` ; en-tête
  `X-Hx-Permissions` posé depuis la session, celui du navigateur est retiré.
- `apps/web` : page Doctrine (question, publication, langue, réponse citée, motif du refus, propositions
  cliquables, glossaire), panneau Doctrine et « Expliquer l'ordre » dans la console.
- `eval/doctrine` et workflow `eval.yml` (manuel et nocturne, runner du serveur) : précision ≥ 94 %, pièges tous
  refusés, médiane ≤ 7,5 s ; le jeu de questions reste hors dépôt.
- Compose : services `rerank` (score lexical par défaut) et `doctrine` (corpus d'exemple par défaut).

### Supprimé

- Web de `legacy/app_v3` remplacé par `apps/web` : accueil, console, vue 3D, `vendor/` three.js ; modèles 3D
  déplacés dans `apps/web/public/models`. Doctrine et registre restent jusqu'aux Lots 4 et 5.
- `legacy/app_v3/web/registre.html`, remplacé par la page Registre.
- `legacy/app_v3/web/` (`doctrine.html`, `doctrine.js`, `app.css`, `favicon.svg`), remplacé par la page Doctrine.

### Reporté

- Pilotage par intentions (`PUT /intents`, plan 1.2.0 § 3.1) : au Lot 2, le contrôleur de flotte reste dans le
  moteur, qui lit l'écart au poste à chaque pas ; `sim-bridge` reçoit les points de route.
- Tests `-m postgres` sur une base jetable désignée par `HX_TEST_DATABASE_URL` (ignorés sinon).

## [0.2.0] — 2026-11-18 — Lot 1 : cœur métier extrait

Recette : faite sur poste par caractérisation contre l'ancien code exécuté en boucle fermée (goldens `legacy` et
`core`), couverture de `core` 96 %. Le test `data` (1 541 messages) et les 3 enregistrements `app_v3` demandent le
serveur : ils passent à la recette du Lot 2, qui se joue de toute façon sur le serveur.

### Ajouté

- `core.grounding` : contrôle d'ancrage des réponses de doctrine (chaque nombre présent dans les extraits cités,
  sigle ou code inconnu de toutes les publications : refus), termes inconnus et propositions « vouliez-vous dire ? »,
  motifs de refus ; repris de `legacy/v2/scripts/hx2_service_c.py`, recherche en base fournie par l'appelant ;
  prouvé identique sur un corpus inventé.
- ADR 0006 : dépôt git local, sans remote ni CI hébergée.
- `tools/check.ps1` et `tools/check.sh` : contrôle complet local (équivalent de la CI), seuil de couverture 85 %.
- `tools/backup.ps1` : sauvegarde du dépôt par `git bundle`.
- `packages/core` (`hannibal-core`), avec `signals` (interpréteur) et `orders` (`grammar`, `kinematics`, `recommendations`, `mtp_mapping`), copiés de l’ancien code sans entrée-sortie ; contrat import-linter « Core : aucune entrée-sortie ».
- `core.fleet.control` (`FleetController`) : carotte, rampe au diamètre tactique, virage du bord, postes, sillage,
  évitement, barre manuelle, repris de `server.py` sans ROS, horloge injectée ; prouvé identique à l'ancien serveur
  sur 5 scénarios en boucle fermée.
- `core.scenario` : `ScenarioEngine` (événements, ordres, pistes, exercice, capitaines, barre manuelle, objectifs,
  débrief) repris de `server.py` sans ROS, Docker, threads ni audit, horloge et aléa injectés ; prouvé identique à
  l'ancien serveur sur 11 missions en boucle fermée (les 6 scénarios). Schéma `schema_version: 1` validé au
  chargement ; catalogue migré dans `apps/api/scenarios/`.
- Goldens de caractérisation exécutés sur `legacy` et sur `core` ; écarts voulus du cœur dans `golden/core/`.
- Limite de vitesse unique `SpeedLimits` (3 à 28 nœuds par défaut) pour le clavier et les signaux : un ordre hors
  bornes est ramené à la borne avec une note (le clavier refusait au-delà de 18 nœuds).
- ADR 0007 : back-office métier en .NET 10 (`apps/backoffice`), cœur tactique et IA en Python.
- Socle `apps/backoffice` (.NET 10) : couches Domain / Application / Infrastructure / Api, `/v1/health`, `/v1/ready`
  (sondes PostgreSQL et API, adaptateurs faux ou réels), `/metrics` protégé, `request_id`, `ErrorBody`, jeton interne,
  journal JSON ; 16 tests (contrats JSON Schema partagés, règles de couches) ; image Docker chiseled non root ;
  service dans la composition ; `dotnet format` et `dotnet test` dans pre-commit et `tools/check`.

### Supprimé

- Fichiers obsolètes de `legacy/` (liste dans `legacy/README.md`).

### Modifié

- Crochets pre-commit entièrement hors ligne (`pre-commit-hooks` verrouillé dans `uv.lock`), avec mypy et pytest.
- `.github/workflows/ci.yml` conservé mais inactif.

## [0.1.0] — 2026-11-18 — Lot 0 : fondations

### Ajouté

- Monodépôt : espace de travail uv (Python 3.12) et pnpm, `uv.lock` et `pnpm-lock.yaml` figés.
- `packages/platform` 0.1.0 : configuration typée, journal JSON (structlog), `X-Request-Id`, UUIDv7, erreurs
  `{ code, message, request_id }`, jeton interne, client HTTP interne, `/health`, métriques Prometheus protégées.
- `packages/contracts` 0.1.0 : `ContractModel`, `ErrorBody`, `Health`, `Readiness`, export des schémas JSON
  et test de dérive.
- `apps/api` 0.1.0 : squelette hexagonal, `GET /v1/health`, `GET /v1/ready` (PostgreSQL, Ollama), mode `fake`,
  image Docker non root.
- `infra/compose/compose.dev.yml` : PostgreSQL 17 + pgvector 0.8.7, API, Ollama 0.35.1 (profil `gpu`).
- `eval/characterization` : goldens de l'ancien code (interpréteur, grammaire, cinématique, recommandations,
  pont signaux → ordres), KB synthétique, test sur le jeu réel (marqué `data`), scripts d'enregistrement serveur.
- CI : ruff, mypy strict, import-linter, pytest avec couverture, image API, composition, job Node.
- ADR 0001 à 0005, `docs/developpement.md`, `docs/donnees-hors-depot.md`.

### Modifié

- L'ancien code est déplacé dans `legacy/` ; ses scripts lisent `HANNIBAL_HOME` (défaut `~/hannibal`).
- `.gitignore` adapté à la nouvelle arborescence.
