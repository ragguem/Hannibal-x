#!/bin/bash
cd ~/hannibal/v2; export HX2_EVAL_URL=http://127.0.0.1:8776
while pgrep -f "run_27b.s[h]" >/dev/null; do sleep 30; done
python3 scripts/ask_batch.py eval2/questions2.jsonl eval2/ask_27b_toutes.jsonl > eval2/ask_27b_toutes.log 2>&1; echo "test $(grep BILAN eval2/ask_27b_toutes.log)"
docker rm -f hannibal-hx2-test >/dev/null 2>&1
curl -s -m 180 -X POST http://127.0.0.1:8774/ask -H "Content-Type: application/json" -d "{\"q\":\"What is a column formation?\",\"lang\":\"en\"}" >/dev/null
echo FIN
