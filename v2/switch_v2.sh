#!/bin/bash
# Bascule de l assistant de doctrine (conteneur hannibal-hx2, port 8774) entre deux configurations mesurees.
#   ./switch_v2.sh gemma4   gemma4:12b + tableaux ligne par ligne (scripts/hx2_service_c.py)  — 272/13/15, pieges 29/29, 7 s
#   ./switch_v2.sh gemma3   gemma3:12b + second essai (scripts/hx2_service.py, ancienne configuration) — 264/26/10, pieges 27/29, 9 s
#   ./switch_v2.sh          affiche la configuration active
cd ~/hannibal/v2 || exit 1
case "$1" in
  gemma4) ENVS="-e HX2_QIDX=1 -e HX2_ROWS=1 -e HX2_WORD=1 -e HX_LLM=gemma4:12b -e HX2_THINK=0"; SCRIPT=scripts/hx2_service_c.py ;;
  gemma3) ENVS="-e HX2_QIDX=1"; SCRIPT=scripts/hx2_service.py ;;
  "") echo "Configuration active : $(cat config_active.txt 2>/dev/null || echo inconnue)"; curl -s -m 5 http://127.0.0.1:8774/health | head -c 300; echo; exit 0 ;;
  *) echo "Usage : $0 [gemma4|gemma3]"; exit 2 ;;
esac
docker rm -f hannibal-hx2 >/dev/null 2>&1
docker run -d --name hannibal-hx2 --restart unless-stopped --network host $ENVS -v "$HOME/hannibal/v2/scripts:/v2/scripts:ro" -w /v2 --entrypoint python3 hannibal-v2 $SCRIPT >/dev/null || { echo "ECHEC du demarrage"; exit 1; }
for i in $(seq 1 20); do sleep 1; curl -s -m 2 http://127.0.0.1:8774/health | grep -q "\"ok\": true" && break; done
echo "$1 ($SCRIPT) depuis le $(date "+%Y-%m-%d %H:%M")" > config_active.txt
echo "Sante : $(curl -s -m 5 http://127.0.0.1:8774/health | head -c 220)"
echo "Question test (le premier appel charge le modele, 20 a 40 s)..."
curl -s -m 240 -X POST http://127.0.0.1:8774/ask -H "Content-Type: application/json" -d "{\"q\":\"Which message does the officer in tactical command use to publish the replenishment programme?\",\"lang\":\"en\"}" \
  | python3 -c "import sys,json; r=json.load(sys.stdin); print(\"Reponse :\", r.get(\"status\"), \"|\", r.get(\"llm\"), \"|\", r.get(\"seconds\"), \"s |\", (r.get(\"answer\") or \"\")[:110])"
echo "Configuration active : $(cat config_active.txt)"
