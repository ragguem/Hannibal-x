#!/bin/bash
# 27b compact (IQ3_M) sur le serveur Ollama d essai (11436), service v1 arrete pendant l essai.
cd ~/hannibal/v2; export HX2_EVAL_URL=http://127.0.0.1:8776
docker rm -f hannibal-hx2-test >/dev/null 2>&1; docker run -d --name hannibal-hx2-test --network host -e HX2_PORT=8776 -e HX2_QIDX=1 -e HX2_ROWS=1 -e HX_OLLAMA=http://127.0.0.1:11436 -e HX_LLM=hf.co/bartowski/google_gemma-3-27b-it-GGUF:IQ3_M -e HX_NUM_CTX=6144 -e HX_EMBED_CPU=1 -v $HOME/hannibal/v2/scripts:/v2/scripts:ro -w /v2 --entrypoint python3 hannibal-v2 scripts/hx2_service_c.py >/dev/null; sleep 6
python3 scripts/ask_batch.py eval/questions.jsonl eval/dev_iq3.jsonl > eval/dev_iq3.log 2>&1; echo "dev $(grep BILAN eval/dev_iq3.log)"
docker exec hannibal-ollama-test ollama ps > iq3_ps.txt 2>&1
docker rm -f hannibal-hx2-test hannibal-ollama-test >/dev/null 2>&1; docker start hannibal-hx >/dev/null
curl -s -m 180 -X POST http://127.0.0.1:8774/ask -H "Content-Type: application/json" -d "{\"q\":\"What is a column formation?\",\"lang\":\"en\"}" >/dev/null
echo FIN
