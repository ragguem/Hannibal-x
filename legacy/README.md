# Ancien code (référence fonctionnelle)

Ce dossier contient le code d’avant la refonte, déplacé tel quel au Lot 0. Il reste lançable jusqu’au Lot 6 (arrêt de `app_v3` après la recette du MVP) : une démonstration peut toujours être faite avec lui.

| Dossier | Contenu | Remplacé par |
|---|---|---|
| `app_v3/` | application de travail (port 8773) : console, vue 3D, doctrine, registre | `apps/api`, `apps/web`, `services/sim_bridge` |
| `app/`, `app_v2/` | versions précédentes de l’application | parité de `app_v3` |
| `hx/` | version 1 : interpréteur de signaux, Whisper, RAG v1 | `packages/core/signals`, `services/asr`, `services/doctrine` |
| `v2/` | version 2 : assistant de doctrine (`hx2_service_c.py` en service), reclassement, indexation | `services/doctrine`, `services/rerank` |
| `scripts/` | outils de simulation (flotte, rendu, visualisation) | `services/sim_bridge` |
| `Dockerfile`, `Dockerfile.jazzy`, `patch_sub.py` | messages ROS et relais `ros_tcp_endpoint` | installation LOTUSim |
| `tunnel.sh`, `tunnel_cf.sh` | exposition de la démo sur Internet | retirés, ne pas utiliser à bord |

Règles :

- On ne modifie plus ce code, sauf correctif bloquant pour une démonstration.
- Les scripts supposent le code déployé à plat sous `~/hannibal` sur le serveur. Pour les lancer depuis ce dépôt : `export HANNIBAL_HOME=<dépôt>/legacy`.
- Les images ROS se construisent depuis la racine du dépôt, qui contient `interfaces/` :

```bash
docker build -f legacy/Dockerfile.jazzy -t hannibal-relay .
```

La copie figée de l’état d’origine est dans `hannibal-x--dev-oldversion/`, hors de ce dépôt.
