#!/bin/bash
# Lance un script v2 dans le conteneur d'outils (image hannibal-v2 : hannibal-x + pymupdf), reseau de l'hote, sans GPU
# (les embeddings sont calcules par le conteneur hannibal-ollama). Exemples :
#   ~/hannibal/v2/v2run.sh index_passages.py data/passages_MTP-01.jsonl
#   ~/hannibal/v2/v2run.sh index_passages.py --search "station du guide" --pub MTP-01 -k 5
exec docker run --rm --network host -v "$HOME/hannibal/v2:/v2" -w /v2 --entrypoint python3 hannibal-v2 "scripts/$1" "${@:2}"
