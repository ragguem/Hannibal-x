#!/bin/bash
# Apres les tableaux : gemma4:12b comme redacteur (reflexion coupee), jeu de 60. Meme chaine que le service en place.
cd ${HANNIBAL_HOME:-$HOME/hannibal}/v2; export HX2_EVAL_URL=http://127.0.0.1:8776
while ps -eo cmd | grep -E "run_(rows|27b_test|27b)\.sh" | grep -v grep >/dev/null; do sleep 30; done
docker rm -f hannibal-hx2-test >/dev/null 2>&1; docker run -d --name hannibal-hx2-test --network host -e HX2_PORT=8776 -e HX2_QIDX=1 -e HX_LLM=gemma4:12b -e HX2_THINK=0 -v ${HANNIBAL_HOME:-$HOME/hannibal}/v2/scripts:/v2/scripts:ro -w /v2 --entrypoint python3 hannibal-v2 scripts/hx2_service.py >/dev/null; sleep 6
python3 scripts/ask_batch.py eval/questions.jsonl eval/dev_gemma4.jsonl > eval/dev_gemma4.log 2>&1; echo "dev $(grep BILAN eval/dev_gemma4.log)"
docker rm -f hannibal-hx2-test >/dev/null 2>&1
curl -s -m 180 -X POST http://127.0.0.1:8774/ask -H "Content-Type: application/json" -d "{\"q\":\"What is a column formation?\",\"lang\":\"en\"}" >/dev/null
echo FIN
