#!/bin/bash
# Acces en ligne par tunnel rapide Cloudflare (gratuit, sans compte) vers le port protege par mot de passe.
echo "Identifiant : demo    Mot de passe : $(cat ${HANNIBAL_HOME:-$HOME/hannibal}/app_v2/public_password.txt)"
echo "L adresse https://....trycloudflare.com s affiche ci-dessous dans un cadre. Ctrl+C pour couper l acces."
${HANNIBAL_HOME:-$HOME/hannibal}/bin/cloudflared tunnel --no-autoupdate --url http://127.0.0.1:8781 2>&1 | tee ${HANNIBAL_HOME:-$HOME/hannibal}/tunnel_cf.log | grep --line-buffered -v "precheck\|PRE-CHECKS\|Connectivity\|DNS Resolution\|Cloudflare API\|SUMMARY\|curve pref\|default configuration"
echo "Tunnel ferme."
