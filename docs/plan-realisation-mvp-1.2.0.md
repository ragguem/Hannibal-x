# Hannibal X — plan de réalisation du MVP · architecture 1.2.0

Cible : MVP de démonstration, puis déploiement embarqué sur un navire (serveur on-prem pour le moment).
Base : `docs/Hannibal-X_Low-Level-Design_v1.0.0.md` (socle) et `docs/architecture-1.1.0.md` (cible).
Référence fonctionnelle : le code actuel (`app_v3/`, `hx/`, `v2/`), copie figée dans `hannibal-x--dev-oldversion/`.

| Version | Date | Objet |
|---|---|---|
| LLD 1.0.0 | — | socle, inchangé |
| Architecture 1.1.0 | 16 novembre 2026 | cible, inchangée |
| **1.2.0** | 18 novembre 2026 | ce document : corrections de la 1.1.0 au regard du code réel, versions, interopérabilité, lots, stratégie |

```
PRINCIPE DE LA REFONTE
  rien ne se perd    : chaque fonction de app_v3, hx et v2 a une place et un lot (§ 2)
  rien ne casse      : app_v3 reste lançable jusqu'à la parité (étrangleur, § 9)
  rien n'est deviné  : les règles existantes sont figées par des tests avant d'être déplacées
```

## 0. Résumé

- Sept lots, du Lot 0 (fondations) au Lot 6 (durcissement), mènent au **MVP de démonstration, version 1.0.0**. Chaque lot se termine par une démonstration et une étiquette Git `v0.N.0`.
- La 1.1.0 reste la cible. Le § 3 la corrige sur neuf points découverts dans le code : pilotage de la flotte à 2 Hz, capitaines autonomes, exercice de formations, simulation de trajectoires, explication d’un signal, ordre direct du guide, mode démo 3D, matériel réel (32 Go, 6 cœurs), suppression du socket Docker et des tunnels publics.
- L’interopérabilité avec d’autres systèmes est préparée dès le MVP : contrats versionnés (OpenAPI, AsyncAPI, CloudEvents), boîte d’envoi d’intégration, modèle neutre `Maneuver` / `Situation` qui pourra brancher demain un système de combat réel au lieu de LOTUSim (§ 5).
- Toutes les versions sont figées au Lot 0 (§ 4). Le produit suit un seul numéro de version ; les contrats ont le leur.
- Le développement se fait sur un poste Windows sans GPU grâce à des adaptateurs factices, puis sur le serveur GPU avec LOTUSim pour l’intégration (§ 9).

## 1. Ce que fait le système aujourd’hui

Inventaire tiré du code, pas de la documentation.

```
 navigateur ──8773──> app_v3/server.py  (ThreadingHTTPServer, ~1 180 lignes, état global H)
                        │  pages : préparation, console, vue 3D, doctrine, registre
                        │  SSE /events 4 Hz, repli GET /api/state 300 ms
                        │  boucle ROS 2 Hz : scénario, contacts, capitaines, drill, pilotage
                        │
                        ├── HTTP 8772 ──> hx_service.py   Whisper + interpréteur MTP + explication (RAG v1)
                        ├── HTTP 8774 ──> hx2_service_c.py doctrine ──> 8775 rerank, 11435 Ollama, 5433 Postgres
                        ├── ROS 2 ─────> LOTUSim : /poses, /mas_cmd_array, /<navire>/waypoints
                        ├── socket Docker ──> docker restart lotusim
                        └── fichiers ──> audit/audit.jsonl, audit/audio/<cmd>.wav
```

| Point | Constat |
|---|---|
| Matériel de référence | i5-12400F (6 cœurs, 12 fils), 32 Go, RTX 4060 Ti 16 Go, Ubuntu 26.04, Docker 29 |
| Résultats à conserver | interprétation texte 1 541 / 1 541 ; voix 93,1 % (large-v3-turbo + vocabulaire) ; doctrine ≈ 94 % (300 questions, 29 pièges refusés sur 29), 7 s par réponse |
| Sécurité | pas d’authentification sur le port principal ; mot de passe en clair ; socket Docker ; DSN `postgres:hannibal` en dur ; tunnels `localhost.run` et `cloudflared` vers Internet |
| Robustesse | appels bloquants (voix 90 s, explication 150 s, doctrine 180 s) dans les threads HTTP ; état en mémoire perdu au redémarrage ; registre sans pagination |
| Dette | six variantes de `hx2_service_*.py` ; grammaire MTP en double (`mtp.py` et `hxbridge.py`) ; limites de vitesse incohérentes (18, 28, 29 nœuds) ; `ensure_relay()` et `unity_ready` morts |

## 2. Matrice de parité fonctionnelle

Chaque ligne est une fonction du code actuel. Elle sera testée en recette du lot indiqué. Une ligne sans lot n’existe pas.

### Mission et simulation

| Fonction actuelle | Où aujourd’hui | Où demain | Lot |
|---|---|---|---|
| Catalogue des 6 scénarios YAML (titre, niveau, briefing, flotte, slots) | `GET /api/scenarios` | `ListScenarios`, `GET /v1/scenarios`, schéma YAML validé | 2 |
| Démarrage : choix du scénario, du navire joueur, options capitaines autonomes et barre manuelle, progression « moteur, navires » | `POST /api/start`, `steps` | `StartMission`, événement SSE `phase` avec étapes | 2 |
| Arrêt et retrait des navires | `POST /api/stop` | `StopMission` | 2 |
| Événements temporisés : radio, apparition de pistes | `server.py` boucle 2 Hz | `core.scenario.engine` | 1 |
| Événements conditionnels (`apres_repousse`, `delai_s`) | `cond` | `core.scenario.engine` | 1 |
| Pistes avec comportement (blocage, rapports, échec) | `run.contacts` | `core.scenario.tracks` | 1 |
| Objectifs `attendu` (ordre avant t, classe, repoussé, garde), tolérance 90 s | `server.py` | `core.scenario.objectives` | 1 |
| Exercice de formations (étapes aléatoires, indices, fin anticipée) | `drill` | `core.scenario.drill` | 1 |
| Capitaines autonomes et demandes de reconnaissance (investigate, int_speed, int_corpen, int_station, report_station) | `capt`, `requests`, `POST /api/reply` | `core.scenario.captains`, `ReplyRequest` | 1, 2 |
| Mode automatique (capitaines IA + escorte en pilote automatique) | `POST /api/auto` | `SetAutopilot`, `PUT /v1/missions/{id}/autopilot` | 2 |
| Pilotage : waypoints « carotte », rampe DTAC 731 m, virage du bord ordonné, évitement à 260 m, sillage en colonne | `Ros.carrot`, `_ramp` | `core.fleet.control` exécuté par `sim-bridge` (§ 3.1) | 1, 2 |
| Barre manuelle (barre ±1, cap, vitesse, poste) | `POST /api/helm` | `SetHelm` | 2 |
| Classification d’un contact (ami, neutre, hostile, inconnu) | `POST /api/classify` | `ClassifyContact` | 2 |
| Débrief : score, CPA, classifications, rejouer | overlay console | `ReadMission` (bilan), `Debrief` | 2, 3 |
| Monde LOTUSim : création et retrait des navires (`MASCmdArray`), positions (`VesselPositionArray`), waypoints (`SetWaypoints`) | nœud `hannibal_server_v3` | `services/sim_bridge` | 2 |
| Redémarrage du moteur LOTUSim par `docker restart` | socket Docker | retiré ; remise à zéro du monde par ROS (§ 3.6) | 2 |

### Ordres et validation

| Fonction actuelle | Où aujourd’hui | Où demain | Lot |
|---|---|---|---|
| Ordre clavier grammaire simple (CORPEN, TURN, SPEED, FORM, EMERG, ROGER, WILCO, RESUME STATION) | `mtp.py`, `POST /api/order` | `core.orders.grammar` | 1 |
| Signaux MTP → ordres (TURN, CORPEN, SPEED H/Q/G…, FORM 1–4, STATION, TA62, SU12, INT…) | `hxbridge.py` | `core.orders.mtp_mapping` | 1 |
| Interpréteur de signaux déterministe, 7 statuts (`ok`, `unknown_signal`, `spare`, `not_releasable`, `invalid_parameter`, `missing_parameter`, `empty`) | `hx/scripts/interpret.py` | `core.signals` | 1 |
| Trame radio (THIS IS, OVER, EXECUTE TO FOLLOW, I SAY AGAIN), accusés AFFIRMATIVE, NEGATIVE, ROGER, WILCO | `interpret.py`, `hxbridge.py` | `core.signals.frame`, `core.orders.replies` | 1 |
| Ordre texte avec validation (`awaiting_review` → approuvé ou rejeté) | `POST /api/interpret`, `/api/confirm` | `SubmitOrder`, `DecideCommand` | 2 |
| Correction du transcript et ré-interprétation chaînée (`parent`) | `/api/interpret` | `SubmitOrder` avec `parent_id` | 2 |
| Exécution directe par le guide (ordre planifié, recommandation) | `POST /api/order` | `SubmitOrder` `mode=direct` : commande créée et approuvée par le même opérateur, auditée (§ 3.5) | 2 |
| Restriction de l’escorte (pas d’ordre de manœuvre à un autre navire) | `server.py` | `application/policies.py` | 2 |
| Simulation de l’ordre : trajectoires fantômes 60 s, CPA | `POST /api/simulate`, `sim.py` | `SimulateOrder`, `core.orders.kinematics` | 1, 2 |
| Recommandations (pending, EMERG, CPA, station), rafraîchies toutes les 10 s | `POST /api/recommend`, `reco.py` | `Recommend` + événement SSE `recommendation` | 1, 2 |
| Ordre vocal : micro ou fichier WAV, destinataire, transcription Whisper avec vocabulaire et noms des navires | `POST /api/voice` → `hx /voice` | `SubmitVoice` → `services/asr` | 4 |
| Explication d’un ordre par le modèle (RAG v1 sur `hx_chunks`) | `POST /api/explain` → `hx /explain` | `ExplainCommand` → `services/doctrine` `POST /explain` | 5 |
| Audio conservé et réécoutable | `audit/audio/<cmd>.wav` | volume `hannibal-audio`, `GET /v1/audit/{id}/audio` | 4 |

### Doctrine

| Fonction actuelle | Où aujourd’hui | Où demain | Lot |
|---|---|---|---|
| Question FR ou EN, réponse citée (publication, article, page) ou refus | `hx2 /ask` | `QueryDoctrine` → `services/doctrine` | 5 |
| Reformulation EN, recherche dense `v2.passages`, index de questions `v2.pquestions`, lignes de tableaux `v2.prows` | `hx2_service_c.py` | `AskDoctrine` (étapes injectées) | 5 |
| Reclassement `bge-reranker-v2-m3` entraîné, 60 passages, top 10 | `rerank_service.py` | `services/rerank` | 5 |
| Seuil de score 0,45 sans appel au modèle ; citations obligatoires ; détection d’esquive ; ancrage des nombres ; termes inconnus ; vérification ; second essai sur 3 extraits ; modèle de repli | `hx2_service_c.py` | `EvidenceValidation` + `AskDoctrine` | 5 |
| Style `quotes` (citations mot à mot vérifiées) | `ask_quotes` | option `style` de `POST /ask` | 5 |
| Suggestions orthographiques cliquables | `add_suggestions` | réponse de `/ask`, composant `Answer` | 5 |
| Filtre de publications ; publication classifiée (ATP-28) exclue par défaut | `HX2_CLASSIFIED`, `DOC_PUBS` | permission `doctrine:classified`, `PublicationSelect` | 5 |
| Glossaire OTAN | `/glossary` | `SearchGlossary` | 5 |
| Trace complète (modèle, condensat, consigne, index, réglages) | réponse JSON, audit fichier | `ops.doctrine_traces` | 5 |

### Interface et traçabilité

| Fonction actuelle | Où aujourd’hui | Où demain | Lot |
|---|---|---|---|
| Radar 1–16 NM, sillages, fantômes, centrage | `console.js` | `Radar` | 3 |
| Journal radio, encart VHF EN + traduction FR, synthèse vocale EN | `console.js` | `RadioLog`, `useSpeech` | 3 |
| Tableau des navires, objectifs, barre de mission | `console.js` | `ShipTable`, `ObjectiveList`, `MissionBar` | 3 |
| Vue 3D : mer, ciel, modèles GLB, 5 caméras, ambiances, qualité adaptative, barre manuelle | `view3d.js` | `SimView` (code three.js repris tel quel), `HelmOverlay` | 3 |
| Mode démo 3D sans scénario (`?demo`) | `view3d.js` | `SimView` mode démo | 3 |
| Registre agrégé par commande, audio, statut doctrine | `registre.html` | page Registre, `ReadAudit` paginé | 4 |
| Santé des services voix et doctrine | `/api/hx`, `/api/hx2` | `GET /v1/ready` | 2 |

Fonctions **retirées volontairement** : port public à mot de passe en clair, tunnels Internet, `unity_ready`, `ensure_relay`, `app/` et `app_v2/` (remplacées par la parité de `app_v3`), variantes expérimentales `hx2_service_{w,t,s,r,e3}` (leurs options utiles restent possibles par configuration, voir § 3.8).

## 3. Corrections de la 1.1.0

La 1.1.0 reste la cible. Les points suivants la complètent ou la corrigent. Ils sont pris en compte dès les lots concernés et seront reportés dans une architecture 1.2.0 complète à la fin du Lot 6.

### 3.1 Pilotage de la flotte dans `sim-bridge`

Le code actuel envoie des waypoints à chaque navire toutes les 0,5 s (carotte, rampe, évitement). Passer cette boucle par HTTP depuis l’API, navire par navire, ajouterait de la latence et du couplage.

```
api (MissionRunner, 2 Hz)                        sim-bridge (FleetController, 2 Hz)
  scénario, objectifs, capitaines                  pour chaque navire : intention → waypoints
  décide des intentions :                          carotte, rampe DTAC, virage du bord,
    cap, vitesse, formation, poste, barre  ─────>  évitement, sillage en colonne
                      PUT /intents (lot)           SetWaypoints ──> LOTUSim
```

- L’API envoie des **intentions** (`FleetIntent` : cap, vitesse, formation, poste, barre manuelle) en un seul appel par tick, pas des waypoints.
- `sim-bridge` les traduit en waypoints avec `core.fleet.control` (code pur, testé sans ROS).
- Bénéfice pour l’interopérabilité : un futur adaptateur vers un vrai navire reçoit les mêmes intentions (§ 5.3).

### 3.2 Rythmes

| Boucle | 1.1.0 | 1.2.0 | Raison |
|---|---|---|---|
| Lecture de l’état | 300 ms | 250 ms | même rythme que le SSE actuel (4 Hz) |
| Scénario et intentions | 1 s | 500 ms | même rythme que la boucle ROS actuelle |
| Pilotage des waypoints | — | 500 ms dans `sim-bridge` | § 3.1 |
| SSE vers le navigateur | 300 ms | 250 ms, repli `GET` 300 ms après 3 s sans message | identique à `console.js` |

### 3.3 Fonctions ajoutées au contrat public

| Méthode | Chemin | Handler | Permission |
|---|---|---|---|
| POST | `/v1/missions/{id}/orders` | `SubmitOrder` : `text`, `target`, `parent_id`, `mode` (`review` ou `direct`) | `command:submit` (`direct` : rôle guide) |
| POST | `/v1/missions/{id}/simulations` | `SimulateOrder` : trajectoires 60 s, CPA | `command:submit` |
| GET | `/v1/missions/{id}/recommendations` | `Recommend` | propriétaire |
| POST | `/v1/missions/{id}/requests/{rid}/reply` | `ReplyRequest` : accorder ou refuser une demande de capitaine | `command:decide` |
| PUT | `/v1/missions/{id}/autopilot` | `SetAutopilot` | propriétaire |
| POST | `/v1/commands/{id}/explanation` | `ExplainCommand` | `doctrine:ask` |
| GET | `/v1/doctrine/publications` | publications autorisées pour le rôle | `doctrine:ask` |
| GET | `/v1/missions/{id}/debrief` | bilan détaillé | propriétaire ou `mission:read-all` |

`POST /v1/doctrine/questions` accepte en plus `style` (`verify` ou `quotes`). La réponse porte `suggestions`.

### 3.4 Capitaines, exercice, débrief dans le cœur

`packages/core/scenario` regroupe : `engine` (événements), `tracks` (pistes et comportements), `captains` (capitaines autonomes, demandes), `drill` (exercice de formations), `objectives` (attendus, tolérance 90 s), `debrief` (score). Tout est déterministe avec une horloge et un générateur aléatoire injectés : un scénario se rejoue à l’identique en test.

### 3.5 Ordre direct

Le guide exécute aujourd’hui un ordre planifié ou une recommandation sans passer par la fiche de validation. Demain, `mode=direct` crée la commande et l’approuve dans la même transaction, au nom du même opérateur, avec l’audit `approved` (`source=direct`). Le principe « un humain décide » est tenu ; seul l’écran de validation est sauté.

### 3.6 Plus de socket Docker

`docker restart lotusim` disparaît. Au démarrage d’une mission, `sim-bridge` retire les navires existants puis crée ceux du scénario par `MASCmdArray`. Si le moteur doit être redémarré, c’est une action d’exploitation (unité systemd sur l’hôte), signalée par `/v1/ready`. À confirmer avec l’intégrateur LOTUSim (§ 11).

### 3.7 Matériel réel : 32 Go, 6 cœurs, LOTUSim sur la même machine

Les limites du § 15 de la 1.1.0 supposaient 64 Go et 16 cœurs. Valeurs de départ pour la machine réelle, à mesurer au Lot 6 :

| Conteneur | `mem_limit` | `cpus` |
|---|---|---|
| `proxy` | 128m | 0.5 |
| `api` | 1g | 1.5 |
| `asr` | 3g | 2 |
| `doctrine` | 1g | 1 |
| `rerank` | 2g | 1 |
| `ollama` | 6g | 3 |
| `postgres` | 3g | 2 |
| `sim-bridge` | 512m | 1 |
| observabilité (total, Lot 6) | 1g | 1 |
| **réservé à l’hôte et à LOTUSim** | **≈ 14 Go** | **libre** |

`cpus` est un plafond, pas une réservation : la somme peut dépasser 12. La part de LOTUSim (CPU, RAM et éventuellement GPU pour son rendu) est à mesurer dès le Lot 2 : si son rendu utilise la carte, le budget de 13,6 Go de VRAM ne tient plus (§ 11).

### 3.8 Doctrine : une seule version du service, des options

Seul `hx2_service_c.py` est repris. Ses options deviennent la configuration du service `doctrine` (`DOCTRINE_QIDX`, `DOCTRINE_ROWS`, `DOCTRINE_WORD`, seuil, `num_ctx`, modèle de repli). Les idées des variantes (plein texte `tsv` de `_w`, routage par publication de `_e3`) entrent plus tard comme étapes optionnelles, après mesure sur le grand jeu.

### 3.9 Explication d’un signal

`hx /explain` (RAG v1 sur `public.hx_chunks`) est repris par `services/doctrine` (`POST /explain`). La table passe dans le schéma `v1` (`v1.hx_chunks`), en lecture seule pour `hannibal_doctrine`. Le refus sans appel au modèle quand le statut MTP n’est pas `ok` est conservé.

## 4. Versions

### 4.1 Règles

- **Produit** : un seul numéro SemVer pour tout le dépôt (`apps/*`, `services/*`, `packages/*`, images). Lot N livré = `0.N.0`. MVP de démonstration = **`1.0.0`**. Les images portent la version et le SHA (`hannibal/api:1.0.0`, `hannibal/api:1.0.0-<sha>`).
- **Contrats** : versionnés séparément du produit, parce que des systèmes tiers en dépendront (§ 5).
- **Dépendances** : figées au Lot 0 dans `uv.lock` et `pnpm-lock.yaml`. Pendant le MVP, seules les versions correctives (patch) sont acceptées, après CI verte. Une montée de version mineure ou majeure est un ticket avec mesure.
- Les versions ci-dessous sont la base de départ. Le Lot 0 vérifie le dernier correctif disponible de chaque branche et l’inscrit dans les fichiers de verrouillage.

### 4.2 Composants Hannibal

| Composant | Rôle | Version au MVP |
|---|---|---|
| Hannibal X (produit) | ensemble | 1.0.0 |
| `apps/web` | console React | 1.0.0 |
| `apps/api` | API métier | 1.0.0 |
| `services/asr` | transcription | 1.0.0 |
| `services/doctrine` | doctrine, glossaire, explication | 1.0.0 |
| `services/rerank` | reclassement | 1.0.0 |
| `services/sim_bridge` | pont LOTUSim, pilotage | 1.0.0 |
| `packages/core` | règles MTP, ordres, scénario, pilotage, garde-fous | 1.0.0 |
| `packages/contracts` | schémas internes | 1.0.0 |
| `packages/platform` | socle technique commun | 1.0.0 |

### 4.3 Contrats et données

| Contrat ou donnée | Version au MVP | Règle d’évolution |
|---|---|---|
| API publique | `/v1`, OpenAPI `1.0.0` | ajout seul dans `/v1` ; une rupture ouvre `/v2`, `/v1` maintenue une version produit |
| Événements publiés | `v1` par type (`hx.command.approved.v1`), AsyncAPI `1.0.0` | idem, le numéro est dans le type |
| Contrats internes (`packages/contracts`) | `1.0.0` | client et serveur livrés ensemble, CI de contrat |
| Schéma `ops` | révision Alembic, étiquette `ops-1.0.0` | ajout puis retrait sur deux versions |
| Magasin vectoriel `v2` | `index_version` tracée (`v2.index_versions`) | réindexation = nouvelle version |
| Table MTP | empreinte SHA-256 + date d’extraction, renvoyée par `/v1/ready` et dans l’audit | changement = nouvelle empreinte, recette interpréteur |
| Scénarios YAML | `schema_version: 1` dans chaque fichier | validation au chargement |
| Modèles | `gemma4:12b` (condensat Ollama), `bge-m3`, `reranker-hannibal` (version interne `1.0`), Whisper `large-v3-turbo` | tracés dans `doctrine_traces` et l’audit |

### 4.4 Socle technique

| Couche | Composant | Version |
|---|---|---|
| Hôte | Ubuntu Server | 26.04 LTS (référence actuelle) |
| | Docker Engine / Compose | 29.x / v2 (plugin) |
| | Pilote NVIDIA / NVIDIA Container Toolkit | branche 580 / 1.18 |
| | CUDA dans les images GPU / cuDNN | 12.8 / 9 |
| Simulation | ROS 2 | Jazzy (image `ros:jazzy-ros-base`) |
| | LOTUSim, `lotusim_msgs` | version installée à relever au Lot 2 |
| Python | CPython | 3.12 (aligné sur ROS 2 Jazzy, requis par `rclpy` dans `sim-bridge`) |
| | uv | 0.9 |
| API et services | FastAPI | 0.116 |
| | Uvicorn | 0.35 |
| | Pydantic / pydantic-settings | 2.11 / 2.10 |
| | SQLAlchemy / asyncpg / Alembic | 2.0 / 0.30 / 1.16 |
| | psycopg (doctrine) / pgvector-python | 3.2 / 0.4 |
| | httpx | 0.28 |
| | dependency-injector | 4.48 |
| | structlog | 25.4 |
| | argon2-cffi | 25.1 |
| | prometheus-client | 0.22 |
| | PyYAML | 6.0 |
| IA | faster-whisper / CTranslate2 | 1.2 / 4.6 |
| | PyTorch / sentence-transformers | 2.8 / 5.1 |
| | Ollama | 0.35.1 (actuel, conservé) |
| Données | PostgreSQL / pgvector | 17.11 / 0.8.7 (actuels, conservés) |
| Front | Node.js / pnpm | 24 LTS / 10 |
| | React / React DOM | 19.1 |
| | TypeScript | 5.9 |
| | Vite | 7.1 |
| | TanStack Query | 5 |
| | React Router | 7 |
| | openapi-typescript / openapi-fetch | 7 / 0.14 |
| | three.js | r179 (le code 3D actuel est repris, version alignée au Lot 3) |
| Bord | Caddy | 2.10 |
| Qualité | pytest / pytest-asyncio | 8.4 / 1.1 |
| | ruff / mypy / import-linter | 0.12 / 1.17 / 2.3 |
| | Vitest / Playwright / MSW | 3.2 / 1.55 / 2.10 |
| | ESLint | 9 |
| Observabilité (Lot 6) | Prometheus / Grafana | 3.5 LTS / 12.1 |
| | dcgm-exporter / node-exporter | 4.2 / 1.9 |
| Après MVP | Loki / Promtail / Alertmanager | 3.5 / 3.5 / 0.28 |
| | NATS Server (JetStream) | 2.11 |
| | Keycloak (OIDC) | 26 |
| Normes de contrat | OpenAPI / AsyncAPI / CloudEvents / JSON Schema | 3.1 / 3.0 / 1.0.2 / 2020-12 |

## 5. Interopérabilité

Le système parlera à d’autres applications du bord : système de combat ou de commandement, navigation, messagerie tactique, système de formation à terre. Le MVP ne les connecte pas, mais il ne doit rien construire qui l’empêche.

### 5.1 Principes

| Principe | Application dès le MVP |
|---|---|
| Contrat d’abord | OpenAPI 3.1 commité pour `/v1`, AsyncAPI 3.0 pour les événements, JSON Schema pour les scénarios |
| Modèle neutre | `Situation`, `Track`, `Maneuver`, `FleetIntent`, `Command`, `DoctrineAnswer` dans `packages/contracts`, sans type ROS ni LOTUSim |
| Unités et repères | SI en interne (m, m/s, degrés vrais pour les caps), positions WGS 84, horodatage UTC ISO 8601, identifiants UUIDv7 |
| Version dans le nom | `/v1/...`, `hx.<domaine>.<fait>.v1` |
| Idempotence | toute commande entrante porte une clé (`Idempotency-Key` ou `command_id`) |
| Traçabilité de bout en bout | `X-Request-Id` et `traceparent` (W3C Trace Context) propagés et journalisés |

### 5.2 Événements publiés

Un port `EventPublisher` dans l’API. Chaque handler qui change l’état publie un fait métier dans `ops.integration_outbox`, dans la même transaction (même patron que `command_dispatches`).

```
handler ──transaction──> ops.integration_outbox (enveloppe CloudEvents 1.0)
                              │
       MVP                    └──> lu par le flux SSE et par le registre ; personne d'autre
       après MVP              └──> relais ──> NATS JetStream ──> systèmes abonnés
                                         └──> webhooks signés (HMAC) pour les systèmes simples
```

| Type d’événement | Moment |
|---|---|
| `hx.mission.started.v1`, `hx.mission.finished.v1` | début, fin de mission |
| `hx.command.received.v1`, `hx.command.interpreted.v1` | ordre reçu, interprété |
| `hx.command.approved.v1`, `hx.command.rejected.v1` | décision de l’opérateur |
| `hx.command.dispatched.v1`, `hx.command.dispatch_failed.v1` | résultat de l’envoi |
| `hx.contact.classified.v1` | classification d’un contact |
| `hx.doctrine.answered.v1`, `hx.doctrine.refused.v1` | réponse de doctrine (sans le texte des publications) |

NATS JetStream est retenu pour l’après-MVP : un seul binaire, fonctionne sans réseau extérieur, et ses « leaf nodes » permettent une synchronisation navire–terre en mode déconnecté.

### 5.3 Adaptateurs vers d’autres systèmes

```
            ┌────────────── apps/api (métier) ──────────────┐
            │      FleetPort              IntegrationPort    │
            └─────────┬──────────────────────────┬──────────┘
                      │                          │
          ┌───────────┴───────────┐              │
          v                       v              v
   sim-bridge (MVP)       ship-bridge (futur)    gateway (futur)
   ROS 2 ─> LOTUSim       DDS ─> système de      NATS, webhooks,
                          combat réel            NMEA 0183/2000, AIS,
                                                 messagerie tactique (ADatP-3)
```

- `FleetPort` est le seul point par lequel le métier agit sur des navires. Remplacer LOTUSim par un système réel revient à écrire un nouvel adaptateur qui parle `FleetIntent` et `Situation`.
- DDS est déjà présent via ROS 2 ; c’est aussi la norme la plus répandue dans les systèmes de combat navals. Un `ship-bridge` DDS est le chemin le plus court vers un système réel.
- Les normes ADatP-3, NMEA, AIS sont citées comme cibles probables ; leur choix dépend des systèmes du navire (§ 11).

### 5.4 Identité des systèmes

| Étape | Mécanisme |
|---|---|
| MVP | sessions humaines seulement ; pas d’accès machine |
| Après MVP | comptes de service avec clés d’API à portée limitée (`scope`), rotation, audit |
| Cible navire | OIDC (Keycloak) relié à l’annuaire du bord, mTLS entre systèmes avec la PKI du navire |

## 6. Évolutivité

Le MVP tourne sur une machine. La conception permet de grandir sans réécrire.

| Palier | Déclencheur | Changement | Ce qui le rend possible dès le MVP |
|---|---|---|---|
| 1. MVP | démonstration | une machine, Compose, un worker API | — |
| 2. Plusieurs postes opérateurs | plus d’une dizaine de sessions SSE, plusieurs missions | `MissionRunner` sorti dans un processus `mission-engine` ; API à plusieurs workers ; diffusion par `LISTEN/NOTIFY` puis NATS | `MissionRunner` n’est appelé que par ports ; `EventPublisher` déjà en place |
| 3. Deux machines à bord | GPU partagé saturé, ou séparation des rôles | nœud IA (asr, rerank, ollama, doctrine) et nœud applicatif ; Compose par nœud ou k3s | services internes sans état, joints par HTTP et jeton |
| 4. Liaison navire–terre | échange de journaux, mises à jour | NATS leaf node, paquets d’installation signés | registre d’intégration, versions de contrat |

Performances visées au MVP, mesurées par `eval.yml` et la recette du Lot 6 :

| Mesure | Cible |
|---|---|
| Ordre clavier : soumission → fiche affichée | < 300 ms (p95) |
| Ordre vocal : fin de dictée → fiche affichée | < 3 s (p95), avec une question de doctrine en cours |
| Décision → navire en manœuvre (accepté par LOTUSim) | < 1 s (p95) |
| Fraîcheur de la situation à l’écran | ≤ 500 ms |
| Réponse de doctrine | ≈ 7 s médiane, comme aujourd’hui |
| Interprétation texte (1 541 messages) | 100 % |
| Doctrine (grand jeu) | ≥ 94 % |

## 7. Organisation du dépôt pendant la refonte

On travaille dans `hannibal-x-dev/`. Le code actuel reste en place et lançable jusqu’au Lot 6.

```
hannibal-x-dev/
  apps/ services/ packages/ infra/ eval/      nouvelle architecture (1.1.0 § 4)
  legacy/                                     ancien code, déplacé au Lot 0, lançable
    app/ app_v2/ app_v3/ hx/ v2/ scripts/
  interfaces/                                 messages ROS de LOTUSim (gardés, utilisés par sim-bridge)
  docs/
    architecture-1.1.0.md                     cible, inchangée
    Hannibal-X_Low-Level-Design_v1.0.0.md     socle, inchangé
    plan-realisation-mvp-1.2.0.md             ce document
    adr/                                      décisions d'architecture (une par fichier)
  CHANGELOG.md
```

Le déplacement dans `legacy/` se fait en un seul commit, chemins des Dockerfiles et scripts corrigés, et vérifié en relançant `app_v3`. `hannibal-x--dev-oldversion/` reste la copie de référence intouchée.

## 8. Lots

Hypothèse de charge : deux développeurs à temps plein, un accès régulier au serveur GPU avec LOTUSim. Les durées sont des ordres de grandeur, à recaler à la fin du Lot 0.

```
semaines   1   2   3   4   5   6   7   8   9  10  11  12  13  14
Lot 0     ███
Lot 1         ██████
Lot 2                 █████████
Lot 3                     ██████████        (démarre sur le contrat OpenAPI du Lot 2)
Lot 4                             █████
Lot 5                             ███████   (en parallèle du Lot 4)
Lot 6                                         █████
jalons    v0.1   v0.2        v0.3    v0.4  v0.5 v0.6    v1.0.0 MVP
```

Chaque lot a la même fin : CI verte, recette des lignes de la matrice du § 2, démonstration, `CHANGELOG.md`, étiquette Git.

### Lot 0 — Fondations · `v0.1.0` · 1 semaine

But : un dépôt où l’on peut travailler à deux sans se gêner, et des tests qui figent l’existant.

- `git init`, `.gitignore` (données, modèles, `kb/`, audio, secrets), branche `main` protégée, déplacement dans `legacy/`.
- Espace de travail `uv` (Python 3.12), espace `pnpm` (Node 24), `pyproject.toml` racine, `ruff`, `mypy`, `import-linter`, pré-commit.
- `packages/platform` : configuration, journal JSON, `request_id`, jeton interne, client interne, traducteur d’erreurs, `/health`, `/metrics`.
- `packages/contracts` vide mais publié, avec le test de contrat.
- `infra/compose` : profil `dev` (postgres, ollama sur poste avec GPU, sinon factice), profil `dev-fake` (tous les services remplacés par des faux, pour Windows sans GPU).
- CI (`ci.yml`) : lint, types, tests, contrats.
- **Tests de caractérisation** : les 1 541 messages de l’interpréteur ; un enregistrement de 3 scénarios joués par `app_v3` (état toutes les 0,5 s) qui servira de référence au Lot 1 ; un échantillon de 30 questions de doctrine avec leurs réponses actuelles.
- ADR 0001 à 0005 : monodépôt, étrangleur, pilotage dans `sim-bridge`, version unique, contrat d’abord.

Recette : un nouveau développeur clone, lance `uv sync`, `pnpm install`, `compose --profile dev-fake up`, et voit `/health` vert partout.

### Lot 1 — Cœur métier extrait · `v0.2.0` · 2 semaines

But : toutes les règles dans `packages/core`, sans entrée-sortie, prouvées identiques à l’existant.

- `core.signals` depuis `interpret.py` (statuts, trame, groupes).
- `core.orders` : `grammar` (depuis `mtp.py`), `mtp_mapping` (depuis `hxbridge.py`), `replies`, `kinematics` (depuis `sim.py`), `recommendations` (depuis `reco.py`). Une seule limite de vitesse, en configuration.
- `core.scenario` : `engine`, `tracks`, `captains`, `drill`, `objectives`, `debrief` depuis `server.py`, avec horloge et aléa injectés. Schéma YAML `schema_version: 1`, les 6 scénarios migrés et validés.
- `core.fleet.control` : carotte, rampe DTAC, virage du bord, évitement, sillage.
- `core.grounding` : ancrage des nombres et des termes inconnus, motifs de refus.

Recette : 1 541 / 1 541 ; les 3 scénarios rejoués par `core` donnent les mêmes ordres, objectifs et radio que l’enregistrement `app_v3` (tolérance de position fixée dans le test) ; couverture de `core` ≥ 90 %.

### Lot 2 — Mission de bout en bout sans écran · `v0.3.0` · 3 semaines

But : jouer une mission au clavier sur LOTUSim par l’API.

- `services/sim_bridge` : nœud `rclpy` (poses, `MASCmdArray`, `SetWaypoints`), `FleetController` 2 Hz, `PUT /intents`, `POST /maneuvers` idempotent, `GET /state`, registre des manœuvres exécutées, couche anti-corruption.
- `apps/api` : schéma `ops` (Alembic), rôles SQL, comptes locaux et session (Argon2id), RBAC (opérateur, superviseur, admin ; rôle de jeu guide ou escorte), traducteur d’erreurs.
- Handlers : `ListScenarios`, `StartMission`, `StopMission`, `ReadMission`, `SubmitOrder` (`review`, `direct`, `parent_id`), `DecideCommand`, `SimulateOrder`, `Recommend`, `SetHelm`, `ClassifyContact`, `ReplyRequest`, `SetAutopilot`, `ReadAudit`.
- `MissionRunner` (scénario 2 Hz, lecture 4 Hz, SSE), `Dispatcher` et `ops.command_dispatches` (envoi fiable de la 1.1.0), `ops.integration_outbox`.
- OpenAPI `1.0.0` commité **dès la première semaine**, pour débloquer le Lot 3.
- Mesure de la consommation de LOTUSim (CPU, RAM, GPU).

Recette : sur le serveur GPU, le scénario « transit en colonne » se joue de bout en bout par l’API (client généré ou Swagger) ; une panne de `sim-bridge` pendant un envoi est rattrapée sans double exécution ; un redémarrage de l’API reprend les envois en cours.

### Lot 3 — Console React · `v0.4.0` · 3 semaines (chevauche le Lot 2)

But : parité de l’interface hors voix et doctrine.

- Socle front (1.1.0 § 14) : `ApiPort`, `StreamPort`, client généré, TanStack Query, routage, gardes de session.
- Pages : Connexion, Préparation (scénarios, navire, aperçu de formation, options, progression du démarrage), Console (radar, contacts, journal radio et synthèse vocale, objectifs, navires, ordre clavier, simulation, recommandations, demandes des capitaines, mode auto, barre manuelle, débrief), Vue 3D (`view3d.js` enveloppé dans `SimView`, mode démo).
- Développement sur des faux (MSW) tant que l’API du Lot 2 n’est pas prête.
- Tests de bout en bout Playwright sur `dev-fake` : préparation → mission → ordre → validation → débrief.

Recette : un opérateur joue les 6 scénarios au clavier dans la nouvelle console sur LOTUSim, sans retour à `app_v3`.

### Lot 4 — Voix et registre · `v0.5.0` · 1,5 semaine

- `services/asr` : faster-whisper, vocabulaire du domaine et noms des navires de la mission, modèle en configuration (`large-v3-turbo` par défaut, `small` en repli), `compute_type` réglé pour le plafond VRAM.
- `SubmitVoice` : audio stocké, transcription, interprétation, commande `pending`, correction chaînée.
- Front : `VoiceCapture` (maintenir le bouton ou la barre d’espace, import WAV), `InterpretationCard`, accusés.
- Registre : `ReadAudit` paginé, filtres, lecture de l’audio, statut doctrine.

Recette : 93 % sur le jeu de 491 messages audio (même mesure qu’aujourd’hui) ; ordre vocal < 3 s (p95) sur le serveur.

### Lot 5 — Doctrine · `v0.6.0` · 2 semaines (en parallèle du Lot 4)

- `services/rerank` : `reranker-hannibal`, lots de 16, demi-précision.
- `services/doctrine` : `AskDoctrine` repris de `hx2_service_c.py` étape par étape (reformulation, dense, questions, lignes de tableaux, reclassement, seuil, rédaction, `EvidenceValidation`, second essai, modèle de repli, style `quotes`, suggestions), glossaire, `POST /explain` (RAG v1), `v2.index_versions`, rôle SQL en lecture seule, plus aucun mot de passe en dur.
- API : `QueryDoctrine`, `SearchGlossary`, `ExplainCommand`, publications autorisées par rôle, `ops.doctrine_traces`.
- Front : page Doctrine, panneau dans la console, citations, suggestions, glossaire, explication d’un ordre.
- `eval.yml` : grand jeu de 300 questions et 29 pièges.

Recette : ≥ 94 % sur le grand jeu ; 29 pièges refusés sur 29 ; médiane ≈ 7 s ; ATP-28 invisible pour un opérateur.

### Lot 6 — Durcissement et démonstration · `v1.0.0` MVP · 1,5 semaine

- Caddy et TLS (CA interne), un seul port publié, réseaux Docker isolés, secrets dans `/etc/hannibal/`.
- `GpuGate` (priorité à la voix), plafonds VRAM, limites du § 3.7 mesurées et ajustées.
- Audit chaîné par la base (déclencheur de la 1.1.0 § 23) ; ancrages et purge après le MVP.
- Observabilité minimale : `/metrics` partout, Prometheus, Grafana (tableaux Mission et GPU), alerte par la minuterie systemd sur `/v1/ready`.
- Sauvegarde nocturne et test de restauration.
- **Paquet d’installation hors ligne** : images exportées (`docker save`), modèles Ollama et Whisper, SBOM (CycloneDX), sommes de contrôle, script d’installation. Le serveur du navire n’a pas Internet.
- Répétition de démonstration complète deux fois, puis arrêt de `legacy/app_v3`.

Recette : installation à blanc sur une machine vierge depuis le paquet ; démonstration complète (préparation, mission avec voix et validation, doctrine, registre, vue 3D) sans intervention ; toutes les cibles du § 6 tenues.

### Après le MVP

| Version | Contenu |
|---|---|
| 1.1.0 | observabilité complète (Loki, Alertmanager, alertes de la 1.1.0 § 24), ancrages et purge de l’audit, `GpuGate` mesuré |
| 1.2.0 | interopérabilité : relais `integration_outbox` → NATS JetStream et webhooks, comptes de service, AsyncAPI publié |
| 1.3.0 | OIDC (Keycloak), plusieurs opérateurs par mission, essais sur vrais enregistrements radio |
| 2.0.0 | `mission-engine` séparé, API multi-workers, déploiement sur deux nœuds, premier adaptateur vers un système réel |

## 9. Stratégie de développement

### 9.1 Étrangleur

```
Lot 0-1   legacy/app_v3 sert la démo     │  nouveau : core + tests de caractérisation
Lot 2-3   legacy/app_v3 sert la démo     │  nouveau : mission au clavier, console React
Lot 4-5   bascule par fonction           │  voix et doctrine sur la nouvelle plateforme
Lot 6     arrêt de legacy/app_v3         │  MVP 1.0.0
```

Jusqu’au Lot 6, une démonstration peut toujours être faite avec `app_v3`. On ne casse pas l’existant pour avancer le nouveau.

### 9.2 Règles de travail

| Sujet | Règle |
|---|---|
| Branches | développement sur le tronc : branches courtes (≤ 2 jours), demande de fusion obligatoire, `main` toujours déployable |
| Commits | Conventional Commits (`feat(api): …`) ; `CHANGELOG.md` généré à chaque étiquette |
| Revue | une relecture par demande de fusion ; les ADR et les contrats sont relus par les deux développeurs |
| Contrat d’abord | toute nouvelle route commence par l’OpenAPI ; le front avance sur des faux |
| Reprise de code | on déplace d’abord, on améliore ensuite : un commit qui déplace une règle ne la modifie pas |
| Caractérisation | aucune règle n’est déplacée sans test qui fige son comportement actuel |
| Définition de « fait » | tests, types, lint verts ; ligne de la matrice cochée ; documentation à jour ; démonstrable |
| Décisions | une ADR par décision structurante (`docs/adr/NNNN-titre.md`) |

### 9.3 Environnements

| Environnement | Machine | Contenu | Usage |
|---|---|---|---|
| Poste | Windows, sans GPU | `compose --profile dev-fake` : API, Postgres, faux `asr`, faux `doctrine`, faux `sim-bridge` | développement quotidien, front, handlers |
| Intégration | serveur GPU + LOTUSim | `compose --profile dev` complet | tests ROS, voix, doctrine, mesures nocturnes |
| Démonstration | serveur du navire | paquet hors ligne, version étiquetée | répétitions et démonstrations |

Les faux adaptateurs sont du code de production (`infrastructure/fakes/`), injectés par le socle selon la configuration : le même handler tourne sur le poste et sur le serveur.

### 9.4 Tests

| Niveau | Où | Bloquant |
|---|---|---|
| Unitaires `core` et caractérisation | CI | oui |
| Handlers avec ports factices | CI | oui |
| Contrats internes et OpenAPI | CI | oui |
| Intégration SQL (Postgres de test) | CI | oui |
| Front (Vitest) et bout en bout (Playwright sur `dev-fake`) | CI | oui |
| ROS et LOTUSim | serveur d’intégration, à chaque fusion sur `main` | oui à partir du Lot 2 |
| Mesures (interprétation, voix, doctrine, latences) | serveur d’intégration, la nuit | oui à partir du lot concerné : un score qui baisse bloque l’étiquette |

### 9.5 Données hors dépôt

Les publications, `kb/signals.json`, le schéma `v2`, les jeux de mesure et les modèles ne vont jamais dans Git. Le Lot 0 écrit `infra/data/README.md` : où ils sont sur le serveur, comment restaurer `v2` depuis une sauvegarde, comment régénérer `signals.json`. La CI utilise une table MTP et des passages synthétiques.

## 10. Risques

| Risque | Effet | Parade | Lot |
|---|---|---|---|
| Le rendu de LOTUSim utilise le GPU | VRAM insuffisante, doctrine ou voix qui tombe | mesure au Lot 2 ; sinon Whisper `small`, reclassement sur CPU, ou rendu LOTUSim sur une autre machine | 2 |
| Découverte DDS entre `sim-bridge` en conteneur et LOTUSim | pas de positions ni de commandes | `network_mode: host` pour `sim-bridge` seul (1.1.0 § 20), essai dès la semaine 1 du Lot 2 | 2 |
| Comportement du scénario différent après extraction | démo différente de l’actuelle | enregistrements de caractérisation, rejeu automatique | 1 |
| Charge du front sous-estimée (radar, 3D, console de 30 Ko) | retard du Lot 3 | reprise du code three.js tel quel ; console découpée par fonctionnalité | 3 |
| Mémoire vive : 32 Go partagés avec LOTUSim | conteneurs tués | limites du § 3.7, mesures, Ollama limité à 2 modèles | 2, 6 |
| Dépendance à une seule personne pour la doctrine | blocage du Lot 5 | ADR et tests de caractérisation dès le Lot 0, revue croisée | 0, 5 |
| Démonstration sur réseau du navire inconnu | site injoignable | TLS CA interne, un seul port, test d’installation à blanc | 6 |

## 11. Décisions attendues

| Question | Qui | Avant | Proposition |
|---|---|---|---|
| Taille de l’équipe et date de démonstration | direction de projet | Lot 0 | deux développeurs, démonstration en semaine 14 |
| Redémarrage du moteur LOTUSim sans socket Docker | intégrateur LOTUSim | Lot 2 | unité systemd sur l’hôte, déclenchée par l’exploitation |
| Rendu LOTUSim : quelle machine, quel GPU | intégrateur LOTUSim | Lot 2 | mesure, puis choix |
| Systèmes du navire à connecter en premier | métier, intégrateur navire | version 1.2.0 | à recenser ; DDS et NMEA/AIS en candidats |
| Comptes de démonstration et rôles | métier | Lot 2 | un guide, une escorte, un superviseur, un admin |
| Conservation des données à bord | sécurité | Lot 6 | celle proposée par la 1.1.0 § 20 |
