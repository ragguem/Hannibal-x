#!/bin/bash
# FIN DU MODE DEMO : arrete le reclassement et relance la reconnaissance vocale d'immersa.
docker rm -f hannibal-rerank >/dev/null 2>&1 && echo "reclassement arrete"
docker start immersa-stt-1 >/dev/null && echo "immersa-stt-1 relance"
