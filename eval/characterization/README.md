# Tests de caractérisation

Ils figent le comportement de référence pour que le code ne le change pas par accident. Les goldens ont été
enregistrés sur l'ancien code avant sa suppression ([ADR 0002](../../docs/adr/0002-strangler-fig-legacy.md)) ;
ils ne rejouent plus que `hannibal_core`.

| Fichier | Rôle |
|---|---|
| `cases/*.json` | Entrées, par module |
| `golden/*.json` | Sorties attendues pour ces entrées |
| `fixtures/kb_synthetic.json` | Table de signaux **fictive** : les codes exigés par la grammaire, des sens inventés. Aucun texte de publication. |
| `golden_harness.py` | Rejoue les cas sur `hannibal_core` |
| `regenerate.py` | Réécrit les goldens |
| `test_golden.py` | Compare `hannibal_core` aux goldens |
| `test_testset_data.py` | Score de l'interpréteur sur les 1541 messages réels, marqué `data` |
| `scripts/` | Enregistrements à faire sur le serveur (bibliothèque standard seulement) |

## Modules couverts

| Golden | Fonctions vérifiées | Module |
|---|---|---|
| `interpret` | `interpret` (7 statuts, groupes multiples, TACK, I SAY AGAIN, EXECUTE) | `core.signals` |
| `mtp` | `parse`, `fr_message`, `to_text` | `core.orders.grammar` |
| `sim` | `apply_orders`, `path`, `ghost`, `cpa_now` | `core.orders.kinematics` |
| `reco` | `recommend` (veille, exécuter, accuser, emerg, éviter, station) | `core.orders.recommendations` |
| `hxbridge` | `to_orders`, `fr_signal`, `fix_frame`, `reply_word`, `destination` | `core.orders.mtp_mapping` |
| `fleet` | pilotage de la formation : 5 scénarios en boucle fermée avec une physique simple commune | `core.fleet` |
| `scenario` | événements, ordres du joueur, messages approuvés, pistes, exercice, capitaines, réponses, barre manuelle, `state`, `simulate`, `recommend` : 11 missions sur les 6 scénarios de `apps/api/scenarios/` | `core.scenario` |
| `grounding` | `grounded` (avec et sans recherche par mot entier), termes inconnus, suggestions, réponse vide | `core.grounding` |

## Commandes

```bash
uv run pytest eval                                   # goldens
uv run python eval/characterization/regenerate.py    # réécrire tous les goldens
uv run python eval/characterization/regenerate.py sim reco

# sur le serveur, avec les données hors dépôt
HX_KB=$HANNIBAL_HOME/hx/kb/signals.json HX_TESTSET=$HANNIBAL_HOME/hx/tests/testset.jsonl uv run pytest -m data
```

Régénérer un golden n'est légitime que si le changement de comportement est voulu ; le diff se relit en revue
et l'écart est décrit plus bas. Les flottants sont comparés à 1e-6 près.

## Seuil sur le jeu réel

Le seuil est un nombre de cas réussis par champ (`spoken_text`, `written_text`), sans aucun texte, noté par
`hannibal_core.signals.score_interpretation`. Rien n'est à reporter à la main : au premier passage sur le serveur,
le test écrit sa mesure dans `data_baseline.local.json` (ignoré par git, reste sur le serveur) ; les passages
suivants échouent s'ils font moins bien. Une valeur renseignée dans `data_baseline.json` (commité) prime sur le
fichier local.

## Enregistrements serveur

```bash
python3 scripts/record_doctrine.py --questions questions.jsonl --out /var/lib/hannibal/recordings/doctrine.jsonl
```

Ces fichiers contiennent des messages et des citations de publications : ils restent sur le serveur.

## Particularités conservées de l'ancien code

- `mtp.parse` exige un cap de 1 à 3 chiffres pour CORPEN mais accepte `CORPEN 5` (cap 005).
- `interpret` : `TURN STBD 9 I SAY AGAIN TURN STBD 8` garde le premier énoncé et ne fait qu'avertir.

## Écarts voulus par rapport à l'ancien code

Ces écarts sont déjà dans les goldens.

| Golden | Écart | Décision |
|---|---|---|
| `mtp` | Vitesse : une seule limite `SpeedLimits` (3 à 28 nœuds par défaut, fournie par l'appelant) pour le clavier et les signaux ; hors bornes, l'ordre est ramené à la borne avec une note, au lieu d'être refusé. Nouveau champ `notes` dans le résultat. Seuls changent `SPEED 25` (accepté) et `SPEED 2` (ramené à 3). L'ancien code refusait au-delà de 18 nœuds au clavier et ramenait à 28 nœuds pour les signaux. | 2026-11-18, Lot 1 |
| `scenario` | Même limite de vitesse : dans la mission « transit guide joueur », `ALL SHIPS SPEED 30` est ramené à 28 nœuds (vitesse du guide plafonnée à 20 nœuds) au lieu d'être refusé. | 2026-11-18, Lot 1 |
