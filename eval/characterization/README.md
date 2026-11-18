# Tests de caractérisation

Ils figent le comportement **actuel** de l'ancien code (`legacy/`) pour que la refonte le conserve.
Chaque lot qui réimplémente une fonction branche son nouveau code sur les mêmes cas et les mêmes goldens.

| Fichier | Rôle |
|---|---|
| `cases/*.json` | Entrées, par module |
| `golden/*.json` | Sorties de l'ancien code pour ces entrées |
| `fixtures/kb_synthetic.json` | Table de signaux **fictive** : les codes exigés par la grammaire, des sens inventés. Aucun texte de publication. |
| `legacy_harness.py` | Charge l'ancien code et rejoue les cas |
| `regenerate.py` | Réécrit les goldens |
| `test_golden.py` | Compare l'ancien code aux goldens (garde-fou contre une modification involontaire de `legacy/`) |
| `test_testset_data.py` | Score de l'interpréteur sur les 1541 messages réels, marqué `data` |
| `scripts/` | Enregistrements à faire sur le serveur (bibliothèque standard seulement) |

## Modules couverts

| Module | Fonctions | Nouvel emplacement (plan § 2) |
|---|---|---|
| `legacy/hx/scripts/interpret.py` | `interpret` (7 statuts, groupes multiples, TACK, I SAY AGAIN, EXECUTE) | `core.signals`, `core.signals.frame` |
| `legacy/app_v3/mtp.py` | `parse`, `fr_message`, `to_text` | `core.orders.grammar` |
| `legacy/app_v3/sim.py` | `apply_orders`, `path`, `ghost`, `cpa_now` | `core.orders.kinematics` |
| `legacy/app_v3/reco.py` | `recommend` (veille, exécuter, accuser, emerg, éviter, station) | `core.orders.recommendations` |
| `legacy/app_v3/hxbridge.py` | `to_orders`, `fr_signal`, `fix_frame`, `reply_word`, `destination` | `core.orders.mtp_mapping`, `core.orders.replies` |
| `legacy/app_v3/server.py` (ROS remplacé par des bouchons, horloge simulée) | `Hannibal.control`, `Ros.carrot`, `_ramp`, `turn_side`, `_wake_pt`, `_slots`, `_helm_tick` : 5 scénarios en boucle fermée avec une physique simple commune | `core.fleet.control` |
| `legacy/app_v3/server.py` (`_start` réel sans Docker ni ROS, horloge simulée, aléa initialisé) | `Hannibal` : événements, ordres du joueur, messages approuvés (`confirm`), pistes, exercice, capitaines, réponses, barre manuelle, `state`, `simulate`, `recommend` : 11 missions sur les 6 scénarios | `core.scenario` |
| `legacy/v2/scripts/hx2_service_c.py` (`psycopg` et `requests` remplacés, recherche en base sur un corpus inventé) | `grounded` (avec et sans `HX2_WORD`), `add_suggestions`, `suggest`, `NONE` | `core.grounding` |

## Commandes

```bash
uv run pytest eval                                   # goldens
uv run python eval/characterization/regenerate.py    # réécrire tous les goldens
uv run python eval/characterization/regenerate.py sim reco

# sur le serveur, avec les données hors dépôt
HX_KB=$HANNIBAL_HOME/hx/kb/signals.json HX_TESTSET=$HANNIBAL_HOME/hx/tests/testset.jsonl uv run pytest -m data
```

Régénérer un golden n'est légitime que si le changement de comportement est voulu ; le diff se relit en revue.
Les flottants sont comparés à 1e-6 près.

## Seuil sur le jeu réel

Le seuil est un nombre de cas réussis par champ (`spoken_text`, `written_text`), sans aucun texte. Rien n'est à
reporter à la main : au premier passage sur le serveur, le test écrit sa mesure dans `data_baseline.local.json`
(ignoré par git, reste sur le serveur) ; les passages suivants échouent s'ils font moins bien. Une valeur renseignée
dans `data_baseline.json` (commité) prime sur le fichier local.

```bash
HX_KB=/chemin/kb/signals.json HX_TESTSET=/chemin/tests/testset.jsonl uv run pytest -m data
```

## Enregistrements serveur (Lot 0, à faire une fois)

```bash
python3 scripts/record_app_v3_scenario.py --scenario transit_colonne --seconds 300 --out /var/lib/hannibal/recordings/transit_colonne.jsonl
python3 scripts/record_doctrine.py --questions questions.jsonl --out /var/lib/hannibal/recordings/doctrine.jsonl
```

Ces fichiers contiennent des messages et des citations de publications : ils restent sur le serveur.

## Écarts relevés dans l'ancien code

Les goldens les figent tels quels ; la décision de les corriger se prend dans le lot concerné.

- Plage de vitesse : `mtp.parse` refuse au-delà de 18 nœuds, `hxbridge.to_orders` ramène à 28 nœuds. Corrigé dans le cœur (voir ci-dessous).
- `mtp.parse` exige un cap de 1 à 3 chiffres pour CORPEN mais accepte `CORPEN 5` (cap 005).
- `interpret` : `TURN STBD 9 I SAY AGAIN TURN STBD 8` garde le premier énoncé et ne fait qu'avertir.

## Écarts voulus du cœur

L'ancien code reste vérifié contre `golden/<nom>.json`. Quand le cœur doit s'en écarter, son golden est dans
`golden/core/<nom>.json` (`regenerate.py --core <nom>`) et l'écart est décrit ici.

| Module | Écart | Décision |
|---|---|---|
| `mtp` → `orders.grammar` | Vitesse : une seule limite `SpeedLimits` (3 à 28 nœuds par défaut, fournie par l'appelant) pour le clavier et les signaux ; hors bornes, l'ordre est ramené à la borne avec une note, au lieu d'être refusé. Nouveau champ `notes` dans le résultat. Seuls changent `SPEED 25` (accepté) et `SPEED 2` (ramené à 3). | 2026-11-18, Lot 1 |
| `server.py` → `scenario` | Même limite de vitesse : dans la mission « transit guide joueur », `ALL SHIPS SPEED 30` est ramené à 28 nœuds (vitesse du guide plafonnée à 20 nœuds) au lieu d'être refusé. | 2026-11-18, Lot 1 |
