# Données hors dépôt

Le dépôt ne contient que du code, des contrats, de la documentation et des données **fictives** de test.
Tout ce qui suit vit sur le serveur, jamais dans git. Les motifs correspondants sont dans `.gitignore`
et un crochet pre-commit (`no-data-files`) refuse ces fichiers.

## Ce qui ne doit jamais être commité

| Catégorie | Exemples | Pourquoi |
|---|---|---|
| Publications et textes qui en sont tirés | PDF, tables de signaux, passages, questions et réponses générées, fiches | Diffusion restreinte |
| Modèles | `*.gguf`, `*.safetensors`, `*.onnx`, `*.pt`, condensats Ollama | Volume, licence, traçabilité par condensat |
| Audio | `*.wav`, `*.mp3`, enregistrements de commandes | Voix des opérateurs |
| Registres d'audit et journaux | `audit/audit.jsonl`, `*.log` | Données d'exploitation |
| Enregistrements de caractérisation | scénarios joués, réponses doctrine | Contiennent messages et citations |
| Secrets | `*.env`, `public_password.txt`, clés | Évident |

## Où elles vivent

### Ancien code (jusqu'au Lot 6)

Racine : `HANNIBAL_HOME` (défaut `~/hannibal`) sur le serveur de démonstration.

| Chemin | Contenu |
|---|---|
| `$HANNIBAL_HOME/hx/kb/signals.json` | Table de signaux (interpréteur) |
| `$HANNIBAL_HOME/hx/tests/testset.jsonl` | Jeu de 1541 messages de test |
| `$HANNIBAL_HOME/v2/data/` | Passages extraits des publications |
| `$HANNIBAL_HOME/v2/eval/` | Jeux de questions de mesure |
| `$HANNIBAL_HOME/app_v3/audit/` | Registre d'audit et audio des commandes |
| volume Docker `hannibal_ollama` | Modèles Ollama |
| conteneur `hannibal-pg` | Base PostgreSQL et index pgvector |

### Nouvelle architecture (à partir du Lot 1)

| Chemin | Contenu |
|---|---|
| `/var/lib/hannibal/kb/` | Table de signaux, glossaire, versions signées |
| `/var/lib/hannibal/models/` | Modèles Whisper et reclassement, avec condensats |
| `/var/lib/hannibal/recordings/` | Enregistrements de caractérisation |
| `/var/lib/hannibal/audio/` | Audio des commandes (rétention configurable) |
| `/etc/hannibal/` | Secrets et configuration d'exploitation (droits 0600) |
| volume `pgdata` | Base : missions, audit chaîné, doctrine (schéma `v2`) |

## Tests qui ont besoin de ces données

Marqués `data` et ignorés sans les variables d'environnement :

```bash
HX_KB=$HANNIBAL_HOME/hx/kb/signals.json HX_TESTSET=$HANNIBAL_HOME/hx/tests/testset.jsonl uv run pytest -m data
```

Les tests ordinaires utilisent `eval/characterization/fixtures/kb_synthetic.json` : des codes de signal exigés
par la grammaire et des sens inventés (« Sens fictif n »), sans aucun texte de publication.
