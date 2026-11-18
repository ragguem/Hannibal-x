# HANNIBAL X — base de connaissance MTP 2 et jeu de test

Préparé dans la nuit du 11 au 12 novembre 2026. Tout fonctionne en local, sans service
en ligne. La partie RAG (recherche + LLM) tourne sur le serveur, voir « Sur le serveur ». Ce dossier est indépendant de `app/` et `unity/`,
qui n'ont pas été modifiés.

## Ce qu'il y a dans ce dossier

| Dossier | Contenu |
|---|---|
| `kb/` | La publication MTP 1(D) Vol. II mise en base : `signals.json` (une entrée par signal), `signals.csv` (même table pour tableur), `passages.jsonl` (texte intégral par article, pour le RAG), `extraction_report.json` (compteurs et anomalies) |
| `tests/` | Le jeu de test : `testset.jsonl` et `testset.csv` (message écrit, message parlé, réponse attendue) |
| `audio/` | Les messages de test en audio : `clean/` (voix seule) et `vhf/` (voix + effet radio), `manifest.csv` |
| `expert/` | `relecture_expert.xlsx` à envoyer à l'expert, avec les audios correspondants dans `expert/audio/` |
| `results/` | Mesures de référence (voir « Résultats ») |
| `scripts/` | Les programmes qui ont produit tout le reste |

## La base de connaissance (`kb/`)

Chaque signal porte : le code (`signal`), le texte exact de la publication (`raw`
avec la mise en page d'origine, `meaning` et `full_text` remis sur une ligne), le
chapitre, l'article, la page, l'amendement (`ORIGINAL` ou `CHANGE 1`) et un statut :

- `assigned` : signal avec un sens ;
- `spare` : code imprimé sans sens (ligne vide dans la publication) ;
- `not_releasable` : sens remplacé par « NOT RELEASABLE » dans cette édition.

Aucun texte n'est reformulé. En cas de doute, `raw` fait foi.

Les chapitres 1 (instructions), 2 (pavillons seuls) et 34 (tableaux
supplémentaires) sont des tableaux ou de la prose : ils sont dans `passages.jsonl`
mais pas découpés signal par signal.

## Le jeu de test (`tests/`)

Le générateur fabrique chaque message à partir de la table, donc la bonne réponse
est connue d'avance. Catégories :

| Catégorie | Ce que ça vérifie |
|---|---|
| `clean_param` | Signaux de manœuvre avec paramètres (cap, bord, vitesse, relèvement) |
| `clean_fixed` | Signaux complets sans élément à préciser |
| `needs_params` | Signaux dont le sens contient des blancs : seule l'identification est vérifiée |
| `variant_asr` | Même message avec l'orthographe d'une reconnaissance vocale (ALPHA, NINE…) |
| `err_unknown` | Groupe qui n'existe pas : le système doit le dire |
| `err_spare` | Code sans sens attribué |
| `err_not_releasable` | Contenu non diffusé : réponse « non disponible » |
| `err_out_of_range` | Paramètre hors limites (cap 400, TURN 40) |
| `err_missing_side` | TURN ou CORPEN sans PORT ni STBD |

## Refaire chaque étape

Depuis ce dossier, avec Python 3.10 ou plus :

```bash
# 1. Extraction (nécessite pdftotext : paquet poppler-utils)
python scripts/extract_mtp2.py chemin/vers/mtp_2.pdf kb

# 2. Jeu de test
python scripts/generate_tests.py kb/signals.json tests

# 3. Classeur pour l'expert (pip install openpyxl)
python scripts/build_expert_pack.py kb/signals.json kb/extraction_report.json tests/testset.jsonl expert/relecture_expert.xlsx

# 4. Audio (pip install piper-tts numpy scipy ; voix Piper .onnx dans voices/)
python scripts/generate_audio.py tests/testset.jsonl audio --voices voices --ids tests/audio_ids.txt

# 5. Interpréter un message
python scripts/interpret.py kb/signals.json "CHARLIE THIS IS HANNIBAL TURN STARBOARD NINER OVER"

# 6. Mesurer l'interpréteur sur le texte de référence
python scripts/evaluate.py kb/signals.json tests/testset.jsonl

# 7. Mesure de bout en bout : audio -> Whisper -> interpréteur (pip install faster-whisper)
python scripts/transcribe.py audio/manifest.csv audio results/transcripts.csv --model large-v3-turbo --device cuda
python scripts/evaluate.py kb/signals.json tests/testset.jsonl --transcripts results/transcripts.csv

# 8. Recherche par mots-clés dans la publication
python scripts/search.py kb "reduced tactical diameter"
```

## Sur le serveur

Tout est dans `/home/saif/hannibal/hx` (copie de ce dossier, sans `audio/clean`). Rien
n'a été modifié dans `immersa`, `wasla`, ni dans `~/hannibal/app` et `~/hannibal/scripts`.

| Élément | Détail |
|---|---|
| Conteneur `hannibal-pg` | PostgreSQL 17 + pgvector, port 127.0.0.1:5433, base `hannibal`, table `hx_chunks` (1 765 morceaux, dimension 1024) |
| Conteneur `hannibal-ollama` | Ollama séparé de celui d'immersa, port 127.0.0.1:11435, modèles `bge-m3` (embeddings) et `gemma3:12b` (LLM) |
| Image `hannibal-x` | Python + faster-whisper GPU + psycopg, pour lancer les scripts (`Dockerfile.hx`) |

Les deux conteneurs redémarrent avec le serveur. Au repos, Ollama n'occupe pas le GPU :
les modèles sont déchargés après 2 minutes sans demande. En charge, `gemma3:12b` et
`bge-m3` prennent environ 9,5 Go de mémoire GPU, à côté des 4,9 Go d'immersa.

Commandes, depuis `/home/saif/hannibal/hx` :

```bash
R="docker run --rm --network host --user 1000:1000 -v /home/saif/hannibal/hx:/hx hannibal-x python scripts/rag.py"

$R index kb                                   # reconstruire l'index
$R search "que faire si le sens du virage n'est pas décidé" -n 3
$R explain kb "CHARLIE THIS IS HANNIBAL TURN STARBOARD NINER OVER"

# Whisper sur le GPU
docker run --rm --gpus all --user 1000:1000 -e HF_HOME=/hx/hf_cache -v /home/saif/hannibal/hx:/hx hannibal-x \
  python scripts/transcribe.py audio/manifest.csv audio results/transcripts.csv --model large-v3-turbo --device cuda
```

Pour tout arrêter : `docker stop hannibal-ollama hannibal-pg`. Pour tout retirer :
`docker rm -f hannibal-ollama hannibal-pg` puis `docker volume rm hannibal_ollama hannibal_pg`.

`rag.py explain` enchaîne : interpréteur sans IA (signal, sens exact, référence) →
recherche des passages du même chapitre → LLM pour l'explication anglais/français →
contrôle automatique du bord et des nombres, avec une reprise puis un repli sur le texte
de la publication si le contrôle échoue. Si le signal est inconnu, libre, non diffusable
ou hors limites, le LLM n'est pas appelé.

## Limites à connaître

1. **La procédure radio n'est pas dans ce volume.** Le MTP 2 donne la forme parlée
   des groupes (p. 1-12 : EMERG se dit EMERGENCY, FORM se dit FORMATION, etc.) mais
   pas la trame complète d'un appel. Les trames « THIS IS … OVER » et « EXECUTE TO
   FOLLOW » sont des gabarits à valider ; seule la trame « IMMEDIATE EXECUTE … I SAY
   AGAIN … STANDBY EXECUTE » reprend un exemple imprimé (p. 7-7 et 8-3).
2. **Les blancs « ____ » ne sont pas remplis automatiquement**, sauf pour les
   signaux de manœuvre dont l'en-tête décrit les paramètres. La publication ne dit
   pas, signal par signal, comment un blanc se transmet à la voix : c'est la
   question n° 2 posée à l'expert.
3. **Le jeu de test et l'interpréteur viennent de la même table.** Un score de
   100 % sur le texte prouve que la chaîne est cohérente, pas que l'extraction est
   juste. C'est le rôle de l'onglet « Extraction » du classeur expert.
4. **Les indicatifs ALFA, CHARLIE et DELTA sont aussi des lettres phonétiques.**
   « DELTA THIS IS ALFA EMERGENCY ALFA » se comprend par la position des mots, mais
   une transcription imparfaite peut créer une ambiguïté.
5. **L'audio est synthétique.** L'effet radio est une approximation ; il faudra de
   vrais enregistrements VHF autorisés avant de fixer des objectifs chiffrés.
6. **Le français du LLM n'est pas fiable sans relecture** (voir `results/RESULTATS.md`,
   section 4). Le contrôle automatique ne couvre que le bord et les nombres.
7. **Édition 2003.** À confirmer avec l'expert que c'est bien l'édition en vigueur.

## Diffusion

La publication est NATO-UNCLASSIFIED mais sa lettre de promulgation interdit de la
publier sur un support librement accessible. Ce dossier contient le texte de la
publication : même règle. Ne pas le pousser sur un dépôt public.
