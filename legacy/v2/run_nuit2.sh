#!/bin/bash
# Nuit du 14 nov. : (1) second essai avant refus, (2) autres modeles redacteurs. Rien ne touche au service en place (8774).
cd ${HANNIBAL_HOME:-$HOME/hannibal}/v2; export HX2_EVAL_URL=http://127.0.0.1:8776
svc(){ docker rm -f hannibal-hx2-test >/dev/null 2>&1; docker run -d --name hannibal-hx2-test --network host -e HX2_PORT=8776 -e HX2_QIDX=1 $1 -v ${HANNIBAL_HOME:-$HOME/hannibal}/v2/scripts:/v2/scripts:ro -w /v2 --entrypoint python3 hannibal-v2 scripts/hx2_service_r.py >/dev/null; sleep 6; }
dev(){ python3 scripts/ask_batch.py eval/questions.jsonl eval/$1.jsonl > eval/$1.log 2>&1; echo "$1 $(grep BILAN eval/$1.log)"; }
tst(){ python3 scripts/ask_batch.py eval2/questions2.jsonl eval2/$1.jsonl > eval2/$1.log 2>&1; echo "$1 $(grep BILAN eval2/$1.log)"; }
svc "-e HX2_RETRY=3"; dev dev_retry3; tst ask_retry3_toutes
while pgrep -f "ollama pul[l]" >/dev/null; do sleep 30; done
svc "-e HX_LLM=qwen3:14b -e HX2_THINK=0 -e HX2_RETRY=0"; dev dev_qwen3
svc "-e HX_LLM=phi4:14b -e HX2_RETRY=0"; dev dev_phi4
docker rm -f hannibal-hx2-test >/dev/null 2>&1
# remettre gemma3 en memoire pour le service en place
curl -s -m 120 -X POST http://127.0.0.1:8774/ask -H "Content-Type: application/json" -d "{\"q\":\"What is a column formation?\",\"lang\":\"en\"}" >/dev/null
echo FIN
