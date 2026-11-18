# Hannibal X — architecture du socle

Proposition de construction · un serveur on-prem · une carte GPU · pas de cloud.

```
MÉTIER CONSERVÉ
  ordre vocal ou tapé ──> la table MTP décide ──> l'opérateur valide ──> LOTUSim exécute
  question doctrine   ──> passages retrouvés  ──> réponse citée, sinon refus
```

## 1. Décisions

### Forme : deux applications, quatre services internes

```
        APPLICATIONS                              SERVICES INTERNES
  ┌──────────────┐    ┌───────────────────┐       ┌────────────┬──────────────────┐
  │ web          │───>│ api               │──────>│ asr        │ GPU, Whisper     │
  │ React        │    │ métier, session,  │       │ doctrine   │ chaîne de modèles│
  │ (via Caddy)  │    │ audit, scénario   │       │ rerank     │ GPU, classement  │
  └──────────────┘    └───────────────────┘       │ sim-bridge │ ROS 2, LOTUSim   │
                                                  └────────────┴──────────────────┘
  Règle : processus séparé = ressource propre (GPU, ROS, modèle résident).
          Le métier reste dans l'api. Pas de microservices.
```

### Style : hexagonal et injecté, dans chaque processus

```
  presentation ──> application ──> domain ──> packages/core (règles MTP)
                        │
                      ports  <── implémentés par ── infrastructure
                        ^                            (SQL, HTTP, modèles, ROS)
                        │
  socle/ ── construit les adaptateurs et les injecte
```

Détail par composant : § 17 et § 22.

### Stack

```
  FRONT     React · TypeScript · Vite · TanStack Query · client OpenAPI · SSE
  API       FastAPI · SQLAlchemy 2 async · httpx · un worker Uvicorn
  IA        faster-whisper · Ollama (gemma4:12b, bge-m3) · bge-reranker
  DONNÉES   PostgreSQL 17 + pgvector · Alembic · pgAdmin
  INFRA     Docker Compose · Caddy · systemd · CI/CD (§ 16)
```

### Sécurité

```
  poste ──HTTPS, cookie HttpOnly──> Caddy (seul port publié) ──> api
                                                                  │
      session Argon2id ──> permission à la route ──> politique dans le handler
                                                                  │
  api ──jeton interne──> services, sur réseaux Docker isolés sans sortie

  table MTP, publications : montées depuis le serveur, jamais dans le dépôt ni les images
```

### Erreurs et traces

```
  adaptateur ──> exception typée ──> traducteur unique ──> { code, message, request_id }

  chaque processus ──> journal technique JSON (stdout)
  chaque handler   ──> registre métier audit_events (ajout seul)
```

Écartés : framework d’orchestration RAG, bus de messages, base d’événements, Kubernetes.

## 2. Vue d’ensemble

```
 RÉSEAU DU SITE ┆ SERVEUR ON-PREM
                ┆
 Opérateurs ─443┼──> proxy (Caddy) · TLS · build React
                ┆       │ /v1, SSE
                ┆       v
                ┆      api ───────────── SQL ─────────────────> postgres
                ┆       │                                         ^
                ┆       ├─ audio ──────> asr (GPU)                │
                ┆       │                                         │ SQL, lecture
                ┆       ├─ question ───> doctrine ────────────────┘
                ┆       │                  ├─ prompts ───> ollama (GPU)
                ┆       │                  └─ passages ──> rerank (GPU)
                ┆       │
                ┆       └─ manœuvre ───> sim-bridge ── ROS 2 ──> LOTUSim
                ┆
 Admin ─────SSH─┼──> pgadmin (à la demande) ── SQL ──> postgres
```

- Retours : transcript, réponse citée ou refus, situation des navires.
- `api` → services : HTTP avec jeton interne. Le navigateur ne voit que `proxy`.
- L’interprétation MTP n’est pas un appel réseau : c’est `packages/core`, dans l’`api`.

## 3. Hébergement on-prem

Une machine Ubuntu avec Docker, une carte NVIDIA 16 Go, LOTUSim déjà installé.

- **Réseaux Docker.** `edge` relie `proxy` et `api`. `app` relie `api`, `asr` et `doctrine`. `models` relie `doctrine`, `ollama` et `rerank`. `data` relie `api`, `doctrine`, `postgres` et `pgadmin`. `app`, `models` et `data` sont `internal` : pas de sortie vers l’extérieur. `sim` relie `api` à l’hôte, où écoute `sim-bridge` (réseau de l’hôte, pour ROS 2). Les ports sont au § 13, l’ordre de lancement au § 21.
- **Jeton interne.** Chaque service interne exige l’en-tête `X-Internal-Token`. Un conteneur compromis sur un réseau ne commande pas les autres sans ce secret.
- **Socket Docker.** Aucun conteneur ne le monte. Le relais ROS, s’il reste nécessaire, est un service Compose déclaré, pas un conteneur créé par le code.
- **Secrets.** Un fichier par processus dans `/etc/hannibal/` (`api.env`, `asr.env`, …), droits `0600`, hors du dépôt et des images.
- **Données montées.** `/srv/hannibal/kb` (table MTP, lecture seule pour `api`), `/srv/hannibal/eval` (jeux de mesure). Ces fichiers sont tirés d’une publication à diffusion restreinte.
- **TLS.** Caddy termine le TLS avec le certificat du site, ou sa CA interne déployée sur les postes. Les cookies sont `Secure`.
- **GPU.** `asr`, `rerank` et `ollama` partagent la carte `0`. Budget mesuré : environ 13,6 Go. Ollama tourne avec `OLLAMA_NUM_PARALLEL=1` et `OLLAMA_MAX_LOADED_MODELS=2`.
- **Sauvegarde.** `pg_dump` nocturne et copie du volume audio vers un disque du site (`infra/backup`, minuteries systemd). Une restauration est testée chaque mois sur une base jetable. Les volumes Docker ne sont pas une sauvegarde.
- **Supervision.** Chaque conteneur redémarre seul (`restart: unless-stopped`) et a un `healthcheck`. Une minuterie systemd interroge `/v1/ready` et `nvidia-smi` toutes les minutes et alerte l’exploitation par la messagerie du site. Pas de pile Prometheus en première version.

## 4. Dépôt principal

Un seul dépôt, `hannibal`. Il contient toutes les applications, tous les services et toute la configuration d’exécution.

```
hannibal/
  apps/
    web/                 application React, servie par Caddy
    api/                 application FastAPI, seule session opérateur
  services/
    asr/                 transcription (Whisper, GPU)
    doctrine/            pipeline documentaire
    rerank/              classement des passages (GPU)
    sim_bridge/          pont ROS 2 vers LOTUSim
  packages/
    core/                règles MTP, ordres, cinématique, recommandations, garde-fous
    contracts/           schémas Pydantic des services internes
    platform/            socle technique commun : journal, request_id, jeton interne, traducteur de base
  infra/
    bord/                Caddyfile, Dockerfile (Caddy + build React)
    db/                  Alembic, rôles SQL
    backup/              sauvegarde et restauration (pg_dump, audio), minuteries systemd
    ollama/              modèles attendus
    pgadmin/             servers.json
    compose/             compose.yml, fichiers .env d’exemple
  eval/                  scripts de mesure (les jeux restent sur le serveur)
  .github/workflows/     ci.yml, images.yml, eval.yml, deploy.yml
  pyproject.toml         espace de travail Python (uv)
  docs/architecture.md
```

| Dossier | Nature | Processus Compose |
|---|---|---|
| `apps/web` | application | servie par `proxy` |
| `apps/api` | application | `api` |
| `services/asr` | service interne | `asr` |
| `services/doctrine` | service interne | `doctrine` |
| `services/rerank` | service interne | `rerank` |
| `services/sim_bridge` | service interne | `sim-bridge` |
| `packages/core`, `packages/contracts`, `packages/platform` | bibliothèques | aucun |
| `infra/*` | configuration | `proxy`, `postgres`, `ollama`, `pgadmin`, `migrate` |

Une application a un écran ou une session d’opérateur. Un service interne n’a ni cookie ni page : l’API (ou `doctrine` pour `rerank`) est son seul client. `packages/contracts` est importé des deux côtés de chaque contrat interne : le client de l’API et le serveur du service ne peuvent pas diverger. `packages/platform` évite de recopier cinq fois le journal, le `request_id`, le contrôle du jeton interne et le traducteur d’exceptions. `apps/api` et chaque service ont leur `Dockerfile` dans leur dossier. `apps/web` n’a pas d’image propre : sa build est faite dans l’image `proxy` (`infra/bord/Dockerfile`).

Hors du dépôt : LOTUSim, `/etc/hannibal/*.env`, `/srv/hannibal/kb`, `/srv/hannibal/eval`, les volumes.

Le détail de chaque dossier est au § 17.

## 5. Couches

Chaque processus Python suit les mêmes couches. Une couche n’importe que les couches en dessous d’elle.

```
presentation     routes FastAPI, schémas d'entrée-sortie, dépendances, traducteur d'exceptions
application      handlers, ports (Protocol), politiques, unité de travail
domain           entités et règles du processus, sans entrée-sortie
infrastructure   adaptateurs : SQLAlchemy, clients HTTP, modèles, ROS, journal
socle            composition : construit les adaptateurs, les injecte, lit la configuration
```

- `domain` n’importe rien d’autre que `packages/core` et la bibliothèque standard.
- `packages/platform` n’est importé que par `presentation`, `infrastructure` et `socle`.
- `application` définit les ports qu’elle consomme. `infrastructure` les implémente.
- `presentation` ne connaît que `application`.
- `socle` est le seul module qui connaît à la fois les ports et les adaptateurs.

Ces règles sont vérifiées en CI par `import-linter`. `mypy` vérifie les types, pas les dépendances entre couches.

## 6. Patrons retenus

| Patron | Où | Raison |
|---|---|---|
| Ports et adaptateurs | `application/ports.py`, `infrastructure/` | Remplacer Whisper, Ollama, Postgres ou ROS par un faux dans les tests. |
| Composition root | `socle/composition.py`, `socle/composition.tsx` | Un seul endroit construit les objets. Aucun handler ne fait `new` d’un adaptateur. |
| Handler applicatif | `application/handlers/` | Une classe, une action. Point unique pour la politique, la transaction et l’audit. |
| Unité de travail | `UnitOfWork`, gestionnaire de contexte | `async with uow:` valide en sortie normale, annule sur exception. La présentation ne gère pas les transactions. |
| Dépôt | agrégats persistés | `User`, `Session`, `Mission`, `Command`, `AuditEvent`, `DoctrineTrace`. Pas de dépôt pour la table MTP ni pour la flotte. |
| Politique | `application/policies.py` | Droits sur une ressource, testés sans HTTP. |
| Couche anti-corruption | `services/sim_bridge` | Les types ROS et LOTUSim ne sortent pas de ce service. L’API parle `Situation` et `Maneuver`. |
| Stratégie | adaptateurs de modèles | Changer `gemma4:12b` ou la taille de Whisper modifie la composition, pas le handler. |
| Pipeline explicite | `AskDoctrine` dans `services/doctrine` | L’ordre (reformuler, chercher, reclasser, rédiger, contrôler, vérifier, sinon refuser) se lit dans une méthode. |
| Machine à états | `Command` dans `apps/api/domain` | Les transitions d’un ordre sont fermées et testées. |
| Clé d’idempotence | identifiant de commande | Une manœuvre renvoyée après une panne n’est pas exécutée deux fois. |
| Tâche de fond unique | `MissionRunner` | Horloge du scénario et diffusion SSE, dans le processus API. |

Écartés : médiateur générique, chaîne de responsabilité, CQRS avec base de lecture séparée. Ils cachent l’ordre des étapes sans résoudre un problème présent ici.

## 7. API : handlers et transactions

### Handlers

| Handler | Entrée | Effet | Permission |
|---|---|---|---|
| `Login` | identifiant, mot de passe | crée une session | anonyme |
| `Logout` | cookie | révoque la session | connecté |
| `ReadMe` | cookie | acteur, permissions, publications autorisées | connecté |
| `ListScenarios` | | catalogue YAML | `mission:start` |
| `StartMission` | scénario, navire | monde créé, mission `running` | `mission:start` |
| `StopMission` | mission | monde retiré, mission `finished` | propriétaire ou `mission:read-all` |
| `ReadMission` | mission | dernier état connu, bilan si terminée | propriétaire ou `mission:read-all` |
| `SubmitVoice` | audio | transcript, interprétation, commande `pending` | `command:submit`, propriétaire |
| `SubmitOrder` | texte | interprétation, commande `pending` | `command:submit`, propriétaire |
| `DecideCommand` | approuver ou refuser | envoi au simulateur si approuvé | `command:decide`, propriétaire |
| `SetHelm` | cap ou vitesse | barre de son navire | `helm:use`, propriétaire |
| `ClassifyContact` | contact, classe | classe enregistrée | `contact:classify`, propriétaire |
| `QueryDoctrine` | question, langue, publication | réponse citée ou refus, trace | `doctrine:ask` |
| `SearchGlossary` | terme | définitions | `glossary:read` |
| `ReadAudit` | filtres | registre paginé | propriétaire ou `audit:read-all` |
| `ManageUsers` | créer, désactiver, changer de rôle | comptes | `users:manage` |

Une seule mission peut être `running` : LOTUSim est un seul monde. Un index unique partiel sur `missions(phase) WHERE phase = 'running'` le garantit. Un second `StartMission` reçoit `MissionAlreadyRunning`.

Aucune transaction ne reste ouverte pendant un appel réseau vers un service interne.

### Ordre vocal ou clavier

1. `SubmitVoice` écrit l’audio sur le volume, appelle `asr`, puis interprète le transcript avec `core`.
2. `SubmitOrder` commence directement à l’interprétation.
3. Une transaction enregistre la commande `pending`, son statut de signal et les événements `received`, `transcribed`, `interpreted`, `awaiting_review`.
4. Un signal inconnu, libre, non diffusable ou hors limites est un **résultat**, pas une erreur. La commande est enregistrée avec ce statut. Elle ne peut pas être approuvée.

Un fichier audio sans commande (transaction échouée) est supprimé par la tâche de rétention.

### Décision

```
pending ──refuser──> rejected
pending ──approuver──> dispatching ──succès──> dispatched
                           └──échec──> dispatch_failed ──réessayer──> dispatching
```

1. Transaction 1 : `SELECT … FOR UPDATE` sur la commande. Contrôle de l’état et du propriétaire. Refus : `rejected`, audit, fin. Accord : `dispatching`, `decided_by`, audit `approved`.
2. Appel `FleetPort.dispatch(command_id, maneuver)`. `sim-bridge` ignore un identifiant déjà exécuté.
3. Transaction 2 : `dispatched` et audit `simulator_dispatched`, ou `dispatch_failed` et audit, puis `SimulatorUnavailable`.

Au démarrage (`application/startup.py`), l’API interroge `sim-bridge` pour chaque commande restée `dispatching` et la passe à `dispatched` ou `dispatch_failed`. Un ordre n’est jamais marqué parti sans l’avoir été, ni exécuté deux fois.

### Barre et contacts

`SetHelm` est la barre manuelle de l’opérateur sur son propre navire. Elle n’est pas un ordre MTP et ne passe pas par la validation. Elle est auditée (`helm`). `ClassifyContact` est audité (`contact_classified`).

### Doctrine

`QueryDoctrine` contrôle la permission et les publications autorisées, appelle `DoctrinePort`, puis écrit `doctrine_traces` et l’audit dans une transaction ouverte après la réponse. Un sémaphore limite à une question en cours par processus API. Au-delà : `DoctrineBusy`. La carte ne sert pas deux rédactions en même temps.

### MissionRunner

Tâche de fond démarrée par le cycle de vie FastAPI. Elle n’existe que dans le processus API, d’où un seul worker Uvicorn.

- Toutes les 300 ms : lit `GET /state` sur `sim-bridge`, garde le dernier état en mémoire, le publie aux abonnés SSE.
- Toutes les secondes : avance le scénario (événements, contacts, objectifs) avec les règles de `core`, calcule les recommandations et les publie.
- Les navires non joués sont pilotés par le runner. Ces manœuvres sont auditées `source=scenario`. Elles ne passent pas par la validation : ce ne sont pas des ordres de l’opérateur.
- La classe d’un contact (`ClassifyContact`) est gardée dans l’état du runner et dans l’audit. Elle n’a pas de table propre.
- En fin de mission, le bilan (objectifs, ordres, délais de décision) est calculé depuis l’audit et renvoyé par `ReadMission`.

### Démarrage et tâches périodiques

`application/startup.py` s’exécute avant l’ouverture des routes : une mission restée `running` passe à `interrupted`, puis les commandes restées `dispatching` sont réconciliées avec `sim-bridge`.

`application/retention.py` tourne une fois par jour : sessions expirées, audio orphelin, audio et traces plus vieux que la durée de conservation (§ 20).

## 8. Authentification et autorisation

### Session

- `ops.users` : identifiant, hash Argon2id, rôle, date de désactivation.
- `ops.sessions` : hash du jeton, expiration glissante de huit heures, plafond de douze heures, révocation.
- Cookie `HttpOnly`, `Secure`, `SameSite=Strict`. Une seule origine : pas de CORS.
- Les requêtes `POST`, `PUT`, `DELETE` doivent porter un en-tête `Origin` égal au site. Sinon `Forbidden`.
- Cinq échecs de connexion en quinze minutes pour un identifiant et une adresse : `LoginThrottled` jusqu’à la fin de la fenêtre.
- Désactiver un compte révoque ses sessions dans la même transaction.
- Premier compte administrateur : commande `hannibal-api create-admin` sur le serveur. Pas de compte par défaut dans l’image.

### Permissions

La route déclare une permission. `presentation/deps.py` charge l’acteur et la vérifie avant le handler. Le handler applique ensuite la politique sur la ressource (propriétaire de la mission, publication autorisée).

| Permission | operator | supervisor | admin |
|---|---|---|---|
| `mission:start` | oui | oui | oui |
| `mission:read-all` | | oui | oui |
| `command:submit`, `command:decide` | oui, sa mission | oui, sa mission | oui, sa mission |
| `helm:use`, `contact:classify` | oui, sa mission | oui, sa mission | oui, sa mission |
| `doctrine:ask`, `glossary:read` | oui | oui | oui |
| `doctrine:classified` | | oui | oui |
| `audit:read-all` | | oui | oui |
| `users:manage` | | | oui |

Personne ne décide un ordre sur la mission d’un autre. Un superviseur observe, il ne commande pas.

La liste des publications classifiées est une configuration du serveur. `ReadMe` renvoie les publications autorisées pour le rôle. Le client peut restreindre sa recherche à l’une d’elles, jamais l’élargir.

## 9. Données

### ORM

Les classes SQLAlchemy vivent dans `infrastructure/persistence/orm.py`. Les entités vivent dans `domain/`. `infrastructure/persistence/mappers.py` convertit les deux. Les handlers ne voient que les dépôts et l’unité de travail.

### Schéma `ops`, géré par Alembic

```text
users             id, username unique, password_hash, role, disabled_at, created_at
sessions          id, user_id, token_hash unique, expires_at, absolute_expires_at, revoked_at
missions          id, scenario_id, player_ship, phase, owner_id, started_at, finished_at
commands          id, mission_id, source, transcript, audio_ref, signal_code, signal_status,
                  maneuver jsonb, state, decided_by, decided_at, dispatched_at
audit_events      id, at default now(), actor_id, mission_id, command_id, event, payload jsonb
doctrine_traces   id, at, actor_id, question, language, publication, status, answer,
                  cited jsonb, model, index_version, duration_ms
```

- `missions.phase` : `running`, `finished`, `interrupted`. Index unique partiel sur `running`.
- `commands.source` : `voice`, `keyboard`, `scenario`. `commands.state` : la machine du § 7.
- Index : `commands(mission_id, state)`, `audit_events(mission_id, at)`, `sessions(token_hash)`.
- L’audio est un fichier du volume `hannibal-audio`. La base ne garde que `audio_ref`.
- Le catalogue de scénarios est `apps/api/scenarios/*.yaml`. Il n’est pas en base.

Les passages vectoriels et le glossaire existent déjà, dans leur schéma. Alembic ne les gère pas. Seul le service `doctrine` les écrit, lors d’une réindexation lancée par l’exploitation.

### Rôles SQL

| Rôle | Droits |
|---|---|
| `hannibal_migrator` | DDL sur `ops`. Utilisé par le conteneur `migrate`, jamais par `api`. |
| `hannibal_app` | DML sur `ops`. Sur `audit_events` : `INSERT` et `SELECT` seulement. Aucun droit sur les passages. |
| `hannibal_doctrine` | `SELECT` sur les passages et le glossaire. Utilisé par le service en marche. |
| `hannibal_indexer` | Écriture sur les passages et le glossaire. Utilisé seulement par la commande de réindexation. |
| comptes nominatifs | Humains, via pgAdmin. Lecture par défaut. |

### pgAdmin

Profil Compose `admin` : arrêté par défaut, démarré pour une intervention. Port publié sur `127.0.0.1:5050` seulement, joint par tunnel SSH. Comptes nominatifs, lecture par défaut. On n’y corrige pas une commande ou une ligne d’audit : la chaîne de preuve serait rompue.

## 10. Exceptions

Les adaptateurs attrapent les erreurs techniques (`httpx`, `asyncpg`, ROS) et lèvent une exception de l’application. Une exception de bibliothèque n’atteint pas la route.

```text
HannibalError
  InvalidCredentials
  Unauthenticated
  Forbidden
  NotFound               MissionNotFound, CommandNotFound, ScenarioNotFound
  Conflict               CommandNotPending, MissionAlreadyRunning
  Throttled              LoginThrottled, DoctrineBusy
  DependencyUnavailable  SpeechUnavailable, DoctrineUnavailable, SimulatorUnavailable
  DatabaseUnavailable
```

Un statut de signal MTP (inconnu, libre, non diffusable, hors limites) n’est pas une exception. C’est la réponse normale de l’interpréteur, renvoyée en `200`.

Traducteur unique, `presentation/errors.py` :

| Exception | HTTP | `code` |
|---|---|---|
| `InvalidCredentials` | 401 | `invalid_credentials` |
| `Unauthenticated` | 401 | `unauthenticated` |
| `Forbidden` | 403 | `forbidden` |
| `NotFound` | 404 | `not_found` |
| erreur de validation Pydantic | 422 | `invalid_request` |
| `Conflict` | 409 | `command_not_pending`, `mission_already_running` |
| `Throttled` | 429 | `login_throttled`, `doctrine_busy` |
| `DependencyUnavailable` | 503 | `dependency_unavailable`, avec `dependency` |
| `DatabaseUnavailable` | 503 | `database_unavailable` |
| toute autre | 500 | `internal` |

```json
{ "code": "command_not_pending", "message": "Cette commande n'est plus en attente.", "request_id": "…" }
```

Le message est fixe pour chaque code. Le détail (pile, requête SQL, corps de réponse d’un service) va dans le journal avec `request_id`. Les services internes ont le même traducteur, avec leurs propres codes.

Délais des clients internes : `asr` 60 s, `doctrine` 120 s, `sim-bridge` 5 s, `rerank` 30 s. Un délai dépassé devient `DependencyUnavailable`.

## 11. Journal et registre

### Journal technique

- `structlog`, une ligne JSON par événement, sur stdout, dans tous les processus.
- Champs obligatoires : `ts`, `level`, `service`, `request_id`, `event`. Selon le cas : `actor_id`, `mission_id`, `command_id`, `handler`, `duration_ms`, `status_code`, `dependency`.
- Le middleware de l’API crée `request_id` et le renvoie dans `X-Request-Id`. Les clients internes le transmettent. Chaque service le journalise. Une requête se suit d’un bout à l’autre.
- Rotation par Docker (`json-file`, `max-size`, `max-file`).
- Interdit dans le journal : mot de passe, cookie, jeton interne, audio, texte de publication, prompt complet.
- `info` début et fin de handler ; `warning` refus métier, dépendance lente ; `error` exception non prévue, dépendance tombée.

### Registre métier

Port `AuditLog`. Insert dans `ops.audit_events`, dans la transaction du handler. Événements : `received`, `transcribed`, `interpreted`, `awaiting_review`, `approved`, `rejected`, `simulator_dispatched`, `dispatch_failed`, `helm`, `contact_classified`, `doctrine_answered`, `doctrine_refused`, `mission_started`, `mission_finished`, `login`, `login_failed`, `user_changed`.

`ReadAudit` pagine par mission et par date. La page Registre ne lit que ce handler.

## 12. Contrat HTTP public

Préfixe `/v1`. JSON. Cookie de session. Une seule origine.

| Méthode | Chemin | Handler |
|---|---|---|
| POST | `/v1/sessions` | `Login` |
| DELETE | `/v1/sessions/current` | `Logout` |
| GET | `/v1/me` | `ReadMe` |
| GET | `/v1/scenarios` | `ListScenarios` |
| POST | `/v1/missions` | `StartMission` |
| GET | `/v1/missions/{id}` | `ReadMission` |
| DELETE | `/v1/missions/{id}` | `StopMission` |
| GET | `/v1/missions/{id}/events` | flux SSE du `MissionRunner` |
| POST | `/v1/missions/{id}/voice` | `SubmitVoice` (multipart) |
| POST | `/v1/missions/{id}/orders` | `SubmitOrder` |
| POST | `/v1/commands/{id}/decision` | `DecideCommand` |
| POST | `/v1/missions/{id}/helm` | `SetHelm` |
| POST | `/v1/missions/{id}/contacts/{cid}/classification` | `ClassifyContact` |
| POST | `/v1/doctrine/questions` | `QueryDoctrine` |
| GET | `/v1/glossary?q=` | `SearchGlossary` |
| GET | `/v1/audit` | `ReadAudit` |
| GET | `/v1/audit/{command_id}/audio` | audio d’une commande, même politique que `ReadAudit` |
| GET, POST, PATCH | `/v1/users` | `ManageUsers` |
| GET | `/v1/health` | vivant, sans authentification |
| GET | `/v1/ready` | base joignable, état de chaque service interne |

Flux SSE : événements `situation` (navires, contacts, objectifs), `recommendation`, `command`, `radio`, `phase`, et un battement toutes les 15 s. Caddy ne met pas ce flux en mémoire tampon.

Le schéma OpenAPI est commité. La CI le régénère et échoue en cas d’écart. Le client du front est généré depuis ce fichier.

## 13. Services internes

| Service | Contrat (`packages/contracts`) | Ressource |
|---|---|---|
| `asr` | `POST /transcribe` : audio → transcript, mots, durée | GPU, faster-whisper |
| `doctrine` | `POST /ask`, `GET /glossary` | Ollama, rerank, pgvector |
| `rerank` | `POST /rerank` : question, passages → scores | GPU, bge-reranker |
| `sim-bridge` | `PUT /world`, `DELETE /world`, `GET /state`, `POST /maneuvers` (idempotent par `command_id`), `GET /maneuvers/{id}`, `POST /helm` | ROS 2, LOTUSim |

Ports internes : `api` 8000, `asr` 8001, `doctrine` 8002, `rerank` 8003, `sim-bridge` 8004, `ollama` 11434, `postgres` 5432. Aucun n’est publié sur le réseau du site. Seuls 443 (Caddy) et 22 (SSH) sont ouverts. Le pare-feu de l’hôte refuse 8004 hors de `172.21.0.0/24`.

Chaque service expose `GET /health` et exige `X-Internal-Token`. Aucun n’a de session, de base `ops` ou de règle d’autorisation métier : ces décisions sont prises par l’API avant l’appel.

`sim-bridge` reprend le nœud ROS actuel. Il ne contient pas de scénario : l’horloge et les règles du scénario sont dans le `MissionRunner`.

## 14. Front

### Socle

`apps/web/src/socle/composition.tsx` construit les adaptateurs et les fournit par contexte React.

| Port | Adaptateur | Rôle |
|---|---|---|
| `ApiPort` | `HttpApi` | client généré depuis OpenAPI (`openapi-fetch`) |
| `StreamPort` | `SseStream` | `EventSource` sur la mission active |

Les features passent par `useApi()` et `useStream()`. Elles ne construisent pas d’URL et ne décident jamais si un signal MTP est valide : elles affichent le statut renvoyé par l’API.

### Pages et composants

| Page | Composants |
|---|---|
| Connexion | `LoginForm` |
| Préparation | `ScenarioList`, `ShipPicker`, `FormationPreview`, `StartBar` |
| Console | `MissionBar`, `ObjectiveList`, `Radar`, `ShipTable`, `RadioLog`, `VoiceCapture`, `OrderForm`, `InterpretationCard`, `DecisionBar`, `RecommendationCard`, `Helm`, `ContactCard`, `Debrief` |
| Doctrine | `QuestionForm`, `PublicationSelect`, `Answer`, `CitationList`, `GlossarySearch` |
| Registre | `AuditFilters`, `AuditTable`, `AudioPlayer` |
| Vue 3D | `SimView` (enveloppe du rendu three.js actuel), `HelmOverlay` |
| Administration | `UserTable`, `UserForm` |

`DecisionBar` appelle `POST /v1/commands/{id}/decision`. Elle affiche `dispatch_failed` et propose de réessayer. `PublicationSelect` liste les publications de `GET /v1/me`.

### État

| Donnée | Où |
|---|---|
| Acteur, scénarios, mission, audit, glossaire, utilisateurs | TanStack Query |
| Situation, phase, radio | même cache, écrit par `SseStream` avec `setQueryData` |
| Question doctrine en cours | mutation (`isPending`), bouton bloqué |
| Échelle radar, micro, brouillon | `useState` du composant |

Pas de Redux ni de second store des navires. Les clés de requête sont centralisées dans `socle/query-keys.ts`. Une mutation invalide les clés qu’elle touche. Si le flux SSE tombe, la mission est relue par `GET` toutes les 2 s jusqu’au retour du flux.

### Erreurs

Le client lit `code` et `message`. `401` renvoie à la connexion. `429 doctrine_busy` affiche « assistant occupé ». `503` nomme la dépendance indisponible et propose de réessayer. Une erreur ne vide jamais l’état de la mission.

## 15. Conteneurs

```yaml
# infra/compose/compose.yml — structure
x-common: &common
  restart: unless-stopped
  logging:
    driver: json-file
    options: { max-size: "20m", max-file: "5" }

x-gpu: &gpu
  <<: *common
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            device_ids: ["0"]
            capabilities: [gpu]

networks:
  edge: {}
  app: { internal: true }
  models: { internal: true }
  data: { internal: true }
  sim:                                      # api → sim-bridge sur l'hôte
    ipam: { config: [{ subnet: 172.21.0.0/24, gateway: 172.21.0.1 }] }

services:
  proxy:
    <<: *common
    image: hannibal/proxy:${TAG}            # Caddy + build React
    ports: ["443:443"]
    networks: [edge]
    depends_on: { api: { condition: service_healthy } }
  api:
    <<: *common
    image: hannibal/api:${TAG}
    env_file: /etc/hannibal/api.env
    networks: [edge, app, data, sim]
    extra_hosts: ["sim-bridge:172.21.0.1"]
    volumes:
      - hannibal-audio:/var/lib/hannibal/audio
      - /srv/hannibal/kb:/srv/hannibal/kb:ro
    depends_on: { postgres: { condition: service_healthy } }   # asr, doctrine, sim-bridge : souples (§ 21)
    stop_grace_period: 15s
  asr:
    image: hannibal/asr:${TAG}
    <<: *gpu
    env_file: /etc/hannibal/asr.env
    networks: [app]
  doctrine:
    <<: *common
    image: hannibal/doctrine:${TAG}
    env_file: /etc/hannibal/doctrine.env
    networks: [app, models, data]
    depends_on:
      postgres: { condition: service_healthy }
      rerank: { condition: service_healthy }
      ollama: { condition: service_healthy }
  rerank:
    image: hannibal/rerank:${TAG}
    <<: *gpu
    env_file: /etc/hannibal/rerank.env
    networks: [models]
  ollama:
    image: ollama/ollama:0.35.1
    <<: *gpu
    environment: { OLLAMA_NUM_PARALLEL: "1", OLLAMA_MAX_LOADED_MODELS: "2" }
    volumes: ["ollama-data:/root/.ollama"]
    networks: [models]
  sim-bridge:
    <<: *common
    image: hannibal/sim-bridge:${TAG}
    env_file: /etc/hannibal/sim-bridge.env
    volumes: ["sim-ledger:/var/lib/hannibal/ledger"]
    network_mode: host                      # ROS 2 vers LOTUSim, à valider (§ 20)
    environment: { HTTP_BIND: "172.21.0.1:8004", ROS_AUTOMATIC_DISCOVERY_RANGE: "LOCALHOST" }
  postgres:
    <<: *common
    image: pgvector/pgvector:pg17
    env_file: /etc/hannibal/postgres.env
    volumes: ["pg-data:/var/lib/postgresql/data"]
    networks: [data]
  migrate:
    image: hannibal/api:${TAG}
    command: ["alembic", "upgrade", "head"]
    env_file: /etc/hannibal/migrate.env
    networks: [data]
    depends_on: { postgres: { condition: service_healthy } }
    profiles: [deploy]
  reindex:
    image: hannibal/doctrine:${TAG}
    command: ["hannibal-doctrine", "reindex"]
    env_file: /etc/hannibal/indexer.env
    networks: [models, data]
    profiles: [admin]
  pgadmin:
    image: dpage/pgadmin4
    ports: ["127.0.0.1:5050:80"]
    env_file: /etc/hannibal/pgadmin.env
    networks: [data]
    profiles: [admin]

volumes:
  hannibal-audio:
  sim-ledger:
  ollama-data:
  pg-data:
```

Chaque service a un `healthcheck` sur son `/health`. Les modèles Ollama sont chargés dans `ollama-data` à l’installation : le réseau `models` n’a pas de sortie.

## 16. Qualité, intégration et déploiement

### Tests

| Niveau | Contenu | Où |
|---|---|---|
| Unitaires | `core`, entités, machine à états, politiques | CI, sans GPU |
| Handlers | ports remplacés par des faux injectés | CI, sans GPU |
| Contrats | schémas de `packages/contracts` contre clients et serveurs | CI |
| Intégration | dépôts SQLAlchemy et migrations sur un Postgres de test | CI, conteneur Postgres |
| Front | Vitest, composants avec `ApiPort` factice | CI |
| Mesure | table MTP réelle, jeux de doctrine | serveur GPU, la nuit |

La CI utilise une table MTP synthétique. La table réelle et les jeux de doctrine ne quittent pas le serveur.

### Pipeline

| Workflow | Déclencheur | Étapes |
|---|---|---|
| `ci.yml` | chaque demande de fusion | ruff, mypy, import-linter, pytest, écart OpenAPI, lint et tests front, build front |
| `images.yml` | fusion sur `main` | construction des images, étiquette = SHA, envoi au registre local du site |
| `eval.yml` | nuit, ou manuel, runner du serveur | signaux ≥ 93 %, doctrine ≥ 94 % ; échec si le score baisse |
| `deploy.yml` | manuel, runner du serveur | `TAG=<sha>`, `compose --profile deploy run migrate`, `compose up -d`, contrôle `/v1/ready` |

Retour arrière : redéployer l’étiquette précédente. Les migrations suivent le principe ajout puis retrait sur deux versions, pour qu’une image précédente fonctionne avec le schéma courant.

## 17. Dossiers et socle injecté

Chaque processus a son dossier `socle/`. C’est le seul code qui construit les adaptateurs et les passe aux handlers. Il lit aussi la configuration (`pydantic-settings`, un préfixe par processus). La vue schématique est au § 22.

### `packages/core`

Règles pures, partagées. Pas de socle, pas d’entrée-sortie.

```
packages/core/src/hannibal_core/
  signals/interpreter.py      SignalInterpreter : texte → signal, statut, paramètres
  signals/table.py            chargement de la table MTP depuis un chemin fourni
  orders/grammar.py           ordres tapés (CORPEN, TURN, SPEED, FORM)
  orders/kinematics.py        trajectoires, distance de passage
  orders/recommendations.py   recommandations
  scenario/engine.py          événements, contacts, objectifs, pilotage des navires non joués
  grounding/guard.py          nombres et noms présents dans les extraits
```

### `packages/contracts`

```
packages/contracts/src/hannibal_contracts/
  asr.py                      TranscribeResponse
  doctrine.py                 AskRequest, AskResponse, GlossaryEntry
  rerank.py                   RerankRequest, RerankResponse
  sim.py                      WorldSpec, Situation, Maneuver, Helm
```

### `packages/platform`

Socle technique commun aux cinq processus Python. Pas de règle métier.

```
packages/platform/src/hannibal_platform/
  settings.py                 BaseServiceSettings (pydantic-settings)
  logging.py                  configuration structlog, champs obligatoires du § 11
  request_id.py               middleware : lit ou crée X-Request-Id, le met dans le contexte
  internal_auth.py            dépendance FastAPI : contrôle de X-Internal-Token
  internal_client.py          client httpx : jeton, request_id, délai, erreur → DependencyUnavailable
  errors.py                   HannibalError, DependencyUnavailable, traducteur de base
  health.py                   route GET /health
```

### `apps/web`

Patron : composition par contexte React. Les hooks `use-*` sont les handlers d’écran.

```
apps/web/src/
  socle/
    ports.ts                  ApiPort, StreamPort
    composition.tsx           providers ; seule construction des adaptateurs
    query-client.ts
    query-keys.ts
  app/router.tsx
  app/guards.tsx              RequireSession, RequirePermission (lit GET /v1/me)
  pages/                      login, prep, console, doctrine, registre, vue3d, admin
  features/
    session/                  use-session.ts, LoginForm.tsx
    mission-setup/            use-scenarios.ts, ScenarioList.tsx, ShipPicker.tsx, FormationPreview.tsx, StartBar.tsx
    mission/                  use-mission.ts, MissionBar.tsx, ObjectiveList.tsx, Debrief.tsx
    radar/                    Radar.tsx, ShipTable.tsx, RadioLog.tsx
    voice/                    use-voice.ts, VoiceCapture.tsx
    orders/                   use-order.ts, use-decision.ts, OrderForm.tsx, InterpretationCard.tsx, DecisionBar.tsx
    recommendations/          use-recommendations.ts (lit le cache écrit par le flux), RecommendationCard.tsx
    helm/                     use-helm.ts, Helm.tsx
    contacts/                 use-contact.ts, ContactCard.tsx
    doctrine/                 use-doctrine.ts, use-glossary.ts, QuestionForm.tsx, PublicationSelect.tsx, Answer.tsx, CitationList.tsx, GlossarySearch.tsx
    audit/                    use-audit.ts, AuditFilters.tsx, AuditTable.tsx, AudioPlayer.tsx
    vue3d/                    SimView.tsx, HelmOverlay.tsx
    admin/                    use-users.ts, UserTable.tsx, UserForm.tsx
  components/                 Button, Card, DataTable, Dialog — sans port, sans état serveur
  services/
    http-api.ts               HttpApi
    sse-stream.ts             SseStream, repli en lecture toutes les 2 s
    api-error.ts              lecture de code et message, 401 → connexion
    openapi.d.ts              généré
```

| Port | Adaptateur |
|---|---|
| `ApiPort` | `HttpApi` |
| `StreamPort` | `SseStream` |

### `apps/api`

Patron : conteneur `dependency-injector` (`DeclarativeContainer`). Une route dépend d’un handler. Un handler dépend de ports.

```
apps/api/
  Dockerfile
  scenarios/                  catalogue YAML
  src/hannibal_api/
    main.py                   application, cycle de vie, MissionRunner
    cli.py                    create-admin
    socle/
      settings.py
      composition.py
    presentation/
      middleware.py           request_id, contrôle d'Origin, contexte de journal
      errors.py               traducteur d'exceptions
      deps.py                 acteur, permission
      routes/                 sessions, me, scenarios, missions, commands, doctrine, glossary, audit, users, health
      schemas/
    application/
      ports.py
      policies.py
      handlers/               un fichier par handler du § 7
      mission_runner.py
      startup.py              missions interrompues, réconciliation des commandes dispatching
      retention.py            purge quotidienne
    domain/
      mission.py
      command.py              machine à états
      user.py
      audit.py
      errors.py
    infrastructure/
      persistence/            orm.py, mappers.py, repositories.py, unit_of_work.py
      clients/                asr.py, doctrine.py, sim.py
      audio_store.py
      scenario_catalog.py
      security/               password.py (Argon2id), session_store.py, throttle.py
      clock.py
```

Le journal, le `request_id` et le client interne viennent de `packages/platform`.

| Port | Adaptateur |
|---|---|
| `SignalInterpreter` | `hannibal_core.signals`, table lue dans `/srv/hannibal/kb` |
| `SpeechToText` | `AsrClient` |
| `DoctrinePort` | `DoctrineClient` |
| `FleetPort` | `SimClient` |
| `UnitOfWork` et dépôts | SQLAlchemy async |
| `AuditLog` | dépôt `audit_events` |
| `AudioStore` | volume `hannibal-audio` |
| `ScenarioCatalog` | fichiers `scenarios/*.yaml` |
| `PasswordHasher` | Argon2id |
| `SessionStore` | table `ops.sessions` |
| `LoginThrottle` | mémoire du processus (remise à zéro au redémarrage, acceptable avec un seul worker) |
| `DependencyProbe` | `/health` de chaque client, pour `/v1/ready` |
| `Clock` | horloge système |

### `services/asr`

Patron : un handler, un moteur.

```
services/asr/src/hannibal_asr/
  main.py
  socle/settings.py, composition.py
  presentation/http.py        POST /transcribe, GET /health, jeton interne
  application/ports.py        SpeechEngine
  application/transcribe.py
  infrastructure/whisper.py
```

| Port | Adaptateur |
|---|---|
| `SpeechEngine` | `WhisperEngine` (faster-whisper, vocabulaire du domaine) |

### `services/doctrine`

Patron : pipeline explicite, étapes injectées par le constructeur de `AskDoctrine`.

```
services/doctrine/src/hannibal_doctrine/
  main.py
  socle/settings.py, composition.py
  presentation/http.py        POST /ask, GET /glossary, GET /health
  application/ports.py
  cli.py                      reindex (compte hannibal_indexer), lancé à la main par l'exploitation
  application/ask.py          AskDoctrine
  application/glossary.py
  application/reindex.py      découpe, embeddings, écriture des passages
  infrastructure/
    ollama_chat.py
    ollama_embed.py
    pg_retriever.py
    pg_index_writer.py
    rerank_client.py
```

La réindexation suit les mêmes couches que le service. Elle tourne en commande ponctuelle (service Compose `reindex`, profil `admin`, même image, secrets dans `/etc/hannibal/indexer.env`), pas dans le service en marche. Le service `doctrine` ne détient jamais le mot de passe d’écriture.

| Port | Adaptateur |
|---|---|
| `QueryRewriter`, `Drafter`, `Verifier` | `OllamaChat` |
| `Embedder` | `OllamaEmbed` (`bge-m3`) |
| `Retriever`, `Glossary` | `PgRetriever` |
| `IndexWriter` | `PgIndexWriter` (réindexation seulement) |
| `Reranker` | `RerankClient` |
| `GroundingGuard` | `hannibal_core.grounding` |

### `services/rerank`

Patron : un handler, un modèle.

```
services/rerank/src/hannibal_rerank/
  main.py
  socle/settings.py, composition.py
  presentation/http.py        POST /rerank, GET /health
  application/ports.py        CrossEncoder
  application/rank.py
  infrastructure/bge.py
```

| Port | Adaptateur |
|---|---|
| `CrossEncoder` | `BgeCrossEncoder` |

### `services/sim_bridge`

Patron : couche anti-corruption. Les handlers parlent `Situation` et `Maneuver`. Les messages ROS restent dans `RosVesselBus`.

```
services/sim_bridge/src/hannibal_sim/
  main.py
  socle/settings.py, composition.py
  presentation/http.py        /world, /state, /maneuvers, /helm, /health
  application/ports.py        VesselBus, ManeuverLedger
  application/world.py
  application/dispatch.py     idempotent par command_id ; état d'un identifiant pour la réconciliation
  application/helm.py         barre manuelle
  application/read_state.py
  infrastructure/ros_bus.py   nœud rclpy
  infrastructure/ledger.py    identifiants déjà exécutés
```

| Port | Adaptateur |
|---|---|
| `VesselBus` | `RosVesselBus` |
| `ManeuverLedger` | fichier sur le volume `sim-ledger` |

### `infra`

Pas de handler. Configuration seulement.

```
infra/bord/Caddyfile          site → build React ; /v1 → api ; SSE sans tampon
infra/bord/Dockerfile         étape Node (build apps/web), étape Caddy
infra/db/alembic.ini, env.py, versions/
infra/db/roles.sql            rôles et droits du § 9, appliqué à l'installation
infra/backup/                 pg-dump.sh, audio-sync.sh, restore-test.sh, unités systemd
infra/ollama/models.txt       gemma4:12b, bge-m3, versions figées
infra/pgadmin/servers.json
infra/compose/compose.yml, *.env.example
```

## 18. Reprise de l’existant

| Existant | Devient |
|---|---|
| `hx/scripts/interpret.py` | `packages/core/signals` |
| `app_v3/mtp.py`, `sim.py`, `reco.py` | `packages/core/orders` |
| boucle de scénario de `app_v3/server.py` | `packages/core/scenario` + `MissionRunner` |
| nœud ROS de `app_v3/server.py` | `services/sim_bridge` |
| `hx/scripts/hx_service.py` (transcription seule) | `services/asr` |
| `v2/scripts/hx2_service_c.py` | `services/doctrine`, `AskDoctrine` |
| `v2/scripts/rerank_service.py` | `services/rerank` |
| `app_v3/scenarios/*.yaml` | `apps/api/scenarios/` |
| `app_v3/web/view3d.js` | `SimView` |
| `audit/audit.jsonl` | `ops.audit_events` (reprise unique, si l’historique est conservé) |

`app`, `app_v2` et `app_v3` sont retirés quand la console React couvre la voix, la décision et le registre.

## 19. Ordre de construction

1. Dépôt, espace de travail uv, `packages/core` extrait, `packages/platform`, tests sur table synthétique, `ci.yml`.
2. `apps/api` : schéma `ops`, Alembic, rôles SQL, `Login`, `ReadMe`, traducteur, journal, `create-admin`.
3. `services/sim_bridge`, `StartMission`, `SubmitOrder`, `DecideCommand`, `MissionRunner`. Front : connexion, préparation, console clavier.
4. `services/asr`, `SubmitVoice`.
5. `services/rerank`, `services/doctrine`, `QueryDoctrine`. Front : doctrine et glossaire.
6. Registre, débrief, vue 3D, administration des comptes.
7. `eval.yml` et `deploy.yml` sur le serveur. Arrêt des trois serveurs `http.server`.

## 20. Points ouverts

| Point | À décider avec | Recommandation |
|---|---|---|
| Réseau ROS 2 entre `sim-bridge` et LOTUSim | intégrateur LOTUSim | `network_mode: host` pour `sim-bridge` seul, car LOTUSim tourne sur la même machine et la découverte DDS en conteneur isolé est fragile. Garde-fous : `ROS_DOMAIN_ID` dédié, `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`, HTTP de `sim-bridge` lié à l’adresse du pont Docker seulement, jeton interne, pare-feu de l’hôte. À valider par un essai avant l’étape 3 du § 19. |
| Relais `ros_tcp_endpoint` | intégrateur LOTUSim | S’il est une dépendance de LOTUSim, il appartient à l’installation de LOTUSim (unité systemd), pas à notre Compose. `/v1/ready` le signale indisponible via `sim-bridge`. |
| Forge Git et registre d’images | exploitation | Gitea sur le site, avec son registre de conteneurs et un `act_runner` sur le serveur GPU. Gitea Actions lit la syntaxe des workflows du § 16 sans réécriture majeure. |
| Plusieurs opérateurs sur une mission | métier | Un propriétaire en première version, les superviseurs observent. Si le besoin est confirmé : table `mission_members` et politique élargie, sans toucher aux handlers. |
| Conservation | sécurité, juridique | Proposition à faire valider : audio 90 jours, registre et traces doctrine 2 ans, sessions purgées à 30 jours. Les valeurs sont dans la configuration de `retention.py`. |
| Certificat | exploitation | PKI du site si elle existe. Sinon CA interne de Caddy, racine déployée sur les postes par l’exploitation. Dans les deux cas, ACME est désactivé : le serveur n’a pas d’accès Internet. |

## 21. Ordre de lancement et asynchronisme

### Ordre de lancement

```
déploiement   migrate      attend postgres sain, applique Alembic, s'arrête
                │
étape 1       postgres     sain : pg_isready
                │
étape 2       asr   rerank   ollama        en parallèle, sains quand le modèle est sur le GPU
                │      │        │
étape 3         │   doctrine ◄──┘          attend postgres, rerank, ollama ; préchauffe gemma4 et bge-m3
                │              sim-bridge  aucune attente Compose ; sain quand le nœud ROS tourne
                │
étape 4       api          attend postgres seulement
                │
étape 5       proxy        attend api saine ; le site devient joignable
```

Deux sortes de dépendances :

| Sorte | Liens | Effet si la cible est absente |
|---|---|---|
| Dure (`depends_on: service_healthy`) | `migrate` → `postgres`, `api` → `postgres`, `doctrine` → `postgres`, `rerank`, `ollama`, `proxy` → `api` | le processus ne démarre pas |
| Souple (vérifiée à l’exécution) | `api` → `asr`, `doctrine`, `sim-bridge` ; `sim-bridge` → LOTUSim | le processus démarre ; `/v1/ready` signale la dépendance ; le handler qui en a besoin renvoie `503` |

L’API ne dépend pas durement des services GPU : un modèle lent à charger ne bloque ni la connexion, ni le registre, ni la préparation. LOTUSim est hors Compose ; il peut démarrer avant ou après `sim-bridge`. Tant qu’il est absent, `GET /state` renvoie `simulator: disconnected` et `StartMission` lève `SimulatorUnavailable`.

### Démarrage interne de l’API

Cycle de vie FastAPI (`lifespan`), dans cet ordre :

1. Configuration et journal.
2. Pool `asyncpg`, un client `httpx.AsyncClient` par service interne.
3. `startup.py` : missions `running` passées à `interrupted` (base seule), puis réconciliation des commandes `dispatching` avec `sim-bridge`. Si `sim-bridge` ne répond pas, la réconciliation est relancée toutes les 10 s en tâche de fond ; ces commandes ne peuvent pas être réessayées entre-temps.
4. Tâches de fond : `MissionRunner` (inactif sans mission), rétention (quotidienne).
5. Ouverture des routes. `/v1/health` passe au vert, `proxy` démarre.

### Arrêt

Compose arrête dans l’ordre inverse : `proxy`, puis `api`, puis les services, `postgres` en dernier. L’API refuse les nouvelles requêtes, ferme les flux SSE, laisse 10 s aux requêtes en cours (`stop_grace_period: 15s`), passe la mission active à `interrupted`, arrête ses tâches, ferme le pool.

### Modèle asynchrone

Une boucle d’événements par processus. Toute entrée-sortie est attendue (`await`). Un travail bloquant (inférence GPU, Argon2id, exécuteur ROS) tourne dans un thread, jamais sur la boucle. Il n’y a pas de bus de messages : les seules files sont en mémoire, dans un processus.

| Liaison | Mode | Détail |
|---|---|---|
| navigateur → `api` (actions) | requête-réponse | mutation TanStack, bouton bloqué pendant `isPending` |
| `api` → navigateur | poussée SSE | `MissionRunner` publie dans une `asyncio.Queue` bornée par abonné ; un abonné trop lent est déconnecté et le front relit par `GET` |
| `api` → `asr` | `await`, 60 s | le handler est suspendu, la boucle sert les autres requêtes |
| `api` → `doctrine` | `await`, 120 s, sémaphore de 1 | au-delà : `429 doctrine_busy` |
| `api` → `sim-bridge`, ordre | `await`, 5 s | la réponse signifie « manœuvre acceptée par LOTUSim », pas « terminée » ; l’exécution se voit dans `situation` |
| `api` → `sim-bridge`, état | lecture périodique, 300 ms | tâche du `MissionRunner` |
| `api` → `postgres` | `await` (`asyncpg`) | transactions courtes, jamais ouvertes pendant un appel réseau |
| `api`, Argon2id et écriture audio | thread (`anyio.to_thread`) | environ 100 ms de calcul pour Argon2id |
| `api`, interprétation MTP | dans la boucle | fonction pure, moins d’une milliseconde |
| `asr`, `rerank` : inférence | thread, une à la fois | les requêtes suivantes attendent leur tour |
| `doctrine` : pipeline | `await` successifs | chaque étape dépend de la précédente |
| `sim-bridge` : ROS | exécuteur `rclpy` dans un thread dédié | `/poses` met à jour un état en mémoire ; l’action ROS est rendue à la boucle par une future |

### Séquences

Ordre vocal :

```
navigateur          api                                asr            postgres
 POST /voice ─────> écrit l'audio (thread)
                    await /transcribe ───────────────> inférence (thread)
                    <──────────────────────────────── transcript
                    interprète (core, dans la boucle)
                    transaction ──────────────────────────────────────> commande pending
 <── 200 commande
 <── SSE command
```

Décision :

```
navigateur          api                                sim-bridge             LOTUSim
 POST /decision ──> transaction 1 : dispatching
                    await POST /maneuvers ───────────> action ROS (thread) ──> but
                                                       <───────────────────── but accepté
                    <──────────────────────────────── accepté
                    transaction 2 : dispatched
 <── 200
 <── SSE situation, toutes les 300 ms, le navire manœuvre
```

Question de doctrine :

```
navigateur          api                     doctrine
 POST /questions ─> sémaphore (sinon 429)
                    await /ask ───────────> reformule (ollama)
                                            embeddings (ollama)
                                            cherche (postgres)
                                            reclasse (rerank)
                                            rédige (ollama)
                                            contrôle (core)
                                            vérifie (ollama), sinon refus
                    <──────────────────── réponse citée ou refus
                    transaction : trace et audit
 <── 200
```

Boucle de mission, deux tâches `asyncio` indépendantes pour qu’un `sim-bridge` lent ne retarde pas le scénario :

```
lecture   toutes les 300 ms   await GET /state ──> sim-bridge (état en mémoire)
                              publie situation aux abonnés SSE
scénario  toutes les 1 s      core.scenario : événements, contacts, objectifs, recommandations
                              navires non joués : await POST /maneuvers
                              publie radio, recommendation, phase
```

## 22. Schéma du socle injecté

Vue schématique du § 17. Elle montre qui construit quoi et qui reçoit quoi, sans implémentation.

### Mécanisme commun à chaque processus

```
                 ┌──────────────────── socle/ ────────────────────┐
                 │ settings     lit /etc/hannibal/<processus>.env  │
                 │ composition  construit chaque adaptateur une    │
                 │              fois, puis les passe aux handlers  │
                 └───────────┬──────────────────────┬─────────────┘
                             │ injecte les ports     │ construit
                             v                       v
 presentation ──appelle──> application ──utilise──> ports <──implémente── infrastructure
 routes, erreurs,          handlers,                (Protocol)            SQLAlchemy, httpx,
 contrôle d'accès          politiques,                                    modèles, ROS
                           unité de travail
                                 │
                                 v
                              domain ──> packages/core
                              règles, sans entrée-sortie
```

Le sens des flèches est celui des imports autorisés. Rien ne remonte : le domaine ignore l’application, l’application ignore l’infrastructure. Seul `socle/` connaît à la fois les ports et les adaptateurs.

### `apps/web`

```
┌─ apps/web ─────────────────────── composition par contexte React ─┐
│ socle/   composition.tsx  ── fournit par contexte ──┐              │
│                                                     v              │
│          ApiPort     ──────────────────>  HttpApi (client OpenAPI) │
│          StreamPort  ──────────────────>  SseStream (EventSource)  │
│                                                                    │
│ app/         routeur, gardes de session et de permission           │
│ pages/       assemblent les features                               │
│ features/    use-*  = handlers d'écran, reçoivent les ports        │
│              composants de la feature                              │
│ components/  briques visuelles, sans port ni état serveur          │
│ services/    adaptateurs HttpApi, SseStream, lecture des erreurs   │
└────────────────────────────────────────────────────────────────────┘
```

### `apps/api`

```
┌─ apps/api ──────────── hexagonal, conteneur dependency-injector ──┐
│ socle/   composition.py  ── injecte dans chaque handler ──┐        │
│                                                           v        │
│   SignalInterpreter  ──>  packages/core + table MTP montée         │
│   SpeechToText       ──>  AsrClient        ──> service asr         │
│   DoctrinePort       ──>  DoctrineClient   ──> service doctrine    │
│   FleetPort          ──>  SimClient        ──> service sim-bridge  │
│   UnitOfWork, dépôts ──>  SQLAlchemy async ──> postgres (ops)      │
│   AuditLog           ──>  table audit_events                       │
│   AudioStore         ──>  volume hannibal-audio                    │
│   ScenarioCatalog    ──>  fichiers YAML                            │
│   PasswordHasher     ──>  Argon2id                                 │
│   SessionStore       ──>  table sessions                           │
│   LoginThrottle      ──>  mémoire du processus                     │
│   DependencyProbe    ──>  /health des services                     │
│   Clock              ──>  horloge système                          │
│                                                                    │
│ presentation/    routes, contrôle d'accès, traducteur d'exceptions │
│ application/     handlers, politiques, MissionRunner,              │
│                  démarrage, rétention                              │
│ domain/          Mission, Command (machine à états), User, Audit   │
│ infrastructure/  persistance, clients, sécurité, stockage audio    │
└────────────────────────────────────────────────────────────────────┘
```

### Services internes

```
┌─ services/asr ─────────────────── un handler, un moteur ──┐
│ socle/  ── injecte ──>  SpeechEngine  ──>  WhisperEngine   │
│ presentation/   route de transcription                     │
│ application/    handler de transcription                   │
│ infrastructure/ moteur Whisper (GPU)                       │
└────────────────────────────────────────────────────────────┘

┌─ services/rerank ─────────────────── un handler, un modèle ┐
│ socle/  ── injecte ──>  CrossEncoder  ──>  BgeCrossEncoder │
│ presentation/   route de classement                        │
│ application/    handler de classement                      │
│ infrastructure/ modèle bge-reranker (GPU)                  │
└────────────────────────────────────────────────────────────┘

┌─ services/doctrine ───── pipeline explicite, étapes injectées ─┐
│ socle/  ── injecte dans AskDoctrine ──┐                         │
│                                       v                         │
│   QueryRewriter      ──>  OllamaChat                            │
│   Drafter, Verifier  ──>  OllamaChat                            │
│   Embedder           ──>  OllamaEmbed (bge-m3)                  │
│   Retriever, Glossary──>  PgRetriever (pgvector)                │
│   Reranker           ──>  RerankClient  ──> service rerank      │
│   GroundingGuard     ──>  packages/core                         │
│   IndexWriter        ──>  PgIndexWriter (réindexation seule)    │
│                                                                 │
│ presentation/   routes question et glossaire                    │
│ application/    AskDoctrine, glossaire, réindexation            │
│ infrastructure/ Ollama, pgvector, client rerank                 │
└─────────────────────────────────────────────────────────────────┘

┌─ services/sim_bridge ───────────── couche anti-corruption ROS ─┐
│ socle/  ── injecte ──┐                                          │
│                      v                                          │
│   VesselBus       ──>  RosVesselBus (nœud rclpy) ──> LOTUSim    │
│   ManeuverLedger  ──>  fichier sur le volume sim-ledger         │
│                                                                 │
│ presentation/   routes monde, état, manœuvres, barre            │
│ application/    monde, envoi idempotent, barre, lecture d'état  │
│ infrastructure/ nœud ROS, registre des manœuvres exécutées      │
│                                                                 │
│ Entrée et sortie en Situation et Maneuver ; les types ROS       │
│ restent dans RosVesselBus.                                      │
└─────────────────────────────────────────────────────────────────┘
```

### Bibliothèques partagées

```
            apps/api        services/asr  services/doctrine  services/rerank  services/sim_bridge
               │                 │               │                 │                 │
   ┌───────────┼─────────────────┼───────────────┼─────────────────┼─────────────────┤
   v           v                 v               v                 v                 v
 packages/platform   journal, request_id, jeton interne, client interne, erreurs, santé
                     importé par presentation, infrastructure et socle

 packages/contracts  schémas des appels internes
                     importé par le client (api, doctrine) et par le service appelé

 packages/core       règles MTP, ordres, scénario, garde-fous ; aucune entrée-sortie
                     importé par le domaine de l'api et par doctrine (garde-fous)
```

Ces règles d’import sont vérifiées en CI par `import-linter`.
