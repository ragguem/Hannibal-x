#!/bin/bash
# Apres la mesure du 27b : tableaux ligne par ligne avec le modele en place (gemma3:12b). Une seule variable change : HX2_ROWS=1.
cd ${HANNIBAL_HOME:-$HOME/hannibal}/v2; export HX2_EVAL_URL=http://127.0.0.1:8776
while pgrep -f "run_27b_test.s[h]" >/dev/null || pgrep -f "run_27b.s[h]" >/dev/null; do sleep 30; done
docker rm -f hannibal-hx2-test >/dev/null 2>&1; docker run -d --name hannibal-hx2-test --network host -e HX2_PORT=8776 -e HX2_QIDX=1 -e HX2_ROWS=1 -v ${HANNIBAL_HOME:-$HOME/hannibal}/v2/scripts:/v2/scripts:ro -w /v2 --entrypoint python3 hannibal-v2 scripts/hx2_service_t.py >/dev/null; sleep 6
python3 scripts/ask_batch.py eval/questions.jsonl eval/dev_rows.jsonl > eval/dev_rows.log 2>&1; echo "dev $(grep BILAN eval/dev_rows.log)"
python3 scripts/ask_batch.py eval2/questions2.jsonl eval2/ask_rows_toutes.jsonl > eval2/ask_rows_toutes.log 2>&1; echo "test $(grep BILAN eval2/ask_rows_toutes.log)"
docker rm -f hannibal-hx2-test >/dev/null 2>&1; echo FIN
