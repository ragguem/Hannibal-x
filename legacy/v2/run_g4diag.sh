#!/bin/bash
cd ${HANNIBAL_HOME:-$HOME/hannibal}/v2; export HX2_EVAL_URL=http://127.0.0.1:8776
t(){ docker rm -f hannibal-hx2-test >/dev/null 2>&1; docker run -d --name hannibal-hx2-test --network host -e HX2_PORT=8776 -e HX2_QIDX=1 -e HX_LLM=gemma4:12b -e HX2_THINK=0 $1 -v ${HANNIBAL_HOME:-$HOME/hannibal}/v2/scripts:/v2/scripts:ro -w /v2 --entrypoint python3 hannibal-v2 scripts/hx2_service_c.py >/dev/null; sleep 6
python3 scripts/ask_batch.py eval2/sous_refus_g4.jsonl eval2/g4diag_$2.jsonl > eval2/g4diag_$2.log 2>&1; echo "$2 $(grep BILAN eval2/g4diag_$2.log)"; }
t "-e HX2_ROWS=0" sansrows
t "-e HX2_ROWS=1 -e HX2_K=5" k5
t "-e HX2_ROWS=1 -e HX2_K=6 -e HX2_RETRY=2" k6r2
docker rm -f hannibal-hx2-test >/dev/null 2>&1; echo FIN
