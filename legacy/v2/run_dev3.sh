#!/bin/bash
cd ${HANNIBAL_HOME:-$HOME/hannibal}/v2; export HX2_EVAL_URL=http://127.0.0.1:8776
run(){ docker rm -f hannibal-hx2-test >/dev/null 2>&1; docker run -d --name hannibal-hx2-test --network host -e HX2_PORT=8776 -e HX2_QIDX=1 $1 -v ${HANNIBAL_HOME:-$HOME/hannibal}/v2/scripts:/v2/scripts:ro -w /v2 --entrypoint python3 hannibal-v2 scripts/hx2_service_e3.py >/dev/null; sleep 5; EVAL_EXTRA="$2" python3 scripts/search_eval2.py eval/queries.jsonl eval/$3.jsonl; }
run "-e HX2_GLOSS=1" "{\"route\":false}" dev_g1
run "-e HX2_ROUTE_MIN=5" "{\"route\":true}" dev_r5
echo FIN
