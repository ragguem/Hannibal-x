#!/bin/bash
cd ~/hannibal/v2; export HX2_EVAL_URL=http://127.0.0.1:8776
docker rm -f hannibal-hx2-test >/dev/null 2>&1; docker run -d --name hannibal-hx2-test --network host -e HX2_PORT=8776 -e HX2_QIDX=1 -e HX2_ROWS=1 -e HX_LLM=gemma4:12b -e HX2_THINK=0 -e HX2_THINK_RETRY=1 -v $HOME/hannibal/v2/scripts:/v2/scripts:ro -w /v2 --entrypoint python3 hannibal-v2 scripts/hx2_service_c.py >/dev/null; sleep 6
python3 scripts/ask_batch.py eval2/sous_refus_g4.jsonl eval2/ask_g4think_refus.jsonl > eval2/ask_g4think_refus.log 2>&1; echo "refus $(grep BILAN eval2/ask_g4think_refus.log)"
docker rm -f hannibal-hx2-test >/dev/null 2>&1; echo FIN
