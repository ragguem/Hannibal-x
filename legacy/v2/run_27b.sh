#!/bin/bash
cd ${HANNIBAL_HOME:-$HOME/hannibal}/v2; export HX2_EVAL_URL=http://127.0.0.1:8776
docker exec hannibal-ollama ollama pull gemma3:27b > pull_27b.log 2>&1
docker rm -f hannibal-hx2-test >/dev/null 2>&1; docker run -d --name hannibal-hx2-test --network host -e HX2_PORT=8776 -e HX2_QIDX=1 -e HX_LLM=gemma3:27b -v ${HANNIBAL_HOME:-$HOME/hannibal}/v2/scripts:/v2/scripts:ro -w /v2 --entrypoint python3 hannibal-v2 scripts/hx2_service.py >/dev/null; sleep 6
python3 scripts/ask_batch.py eval2/sous_refus.jsonl eval2/ask_27b_refus.jsonl > eval2/ask_27b_refus.log 2>&1; echo "refus $(grep BILAN eval2/ask_27b_refus.log)"
python3 scripts/ask_batch.py eval/questions.jsonl eval/dev_27b.jsonl > eval/dev_27b.log 2>&1; echo "dev $(grep BILAN eval/dev_27b.log)"
echo FIN
