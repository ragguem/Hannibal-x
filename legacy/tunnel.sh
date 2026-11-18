#!/bin/bash
# Ouvre un acces en ligne a la demo HANNIBAL X, protege par mot de passe. Ctrl+C pour le fermer.
# Seul le port 8781 (avec mot de passe) est expose. Mot de passe : ${HANNIBAL_HOME:-$HOME/hannibal}/app_v2/public_password.txt
echo "Identifiant : demo    Mot de passe : $(cat ${HANNIBAL_HOME:-$HOME/hannibal}/app_v2/public_password.txt)"
echo "L adresse en https s affiche ci-dessous. Fermez cette fenetre (Ctrl+C) pour couper l acces."
exec ssh -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -R 80:127.0.0.1:8781 nokey@localhost.run
