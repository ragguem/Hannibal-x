#!/bin/bash
# MODE DEMO : libere la carte graphique (arrete la reconnaissance vocale d'immersa) et lance le reclassement de HANNIBAL X v2.
docker stop immersa-stt-1 >/dev/null && echo "immersa-stt-1 arrete (immersa n'a plus de reconnaissance vocale tant que demo_off.sh n'est pas lance)"
docker rm -f hannibal-rerank >/dev/null 2>&1
docker run -d --name hannibal-rerank --gpus all --network host -e RERANK_MODEL="${RERANK_MODEL:-BAAI/bge-reranker-v2-m3}" -v "${HANNIBAL_HOME:-$HOME/hannibal}/v2:/v2" -w /v2 --entrypoint python3 hannibal-v2g scripts/rerank_service.py >/dev/null
for i in $(seq 40); do curl -s -m 1 http://127.0.0.1:8775/ >/dev/null && break; sleep 1; done
curl -s -m 2 http://127.0.0.1:8775/ && echo " <- reclassement pret" || echo "reclassement PAS pret : voir docker logs hannibal-rerank"
