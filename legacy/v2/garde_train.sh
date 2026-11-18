#!/bin/bash
# Garde-fou : met en pause la generation (conteneur hannibal-genq) si la carte graphique ou le processeur chauffe trop, la reprend une fois refroidi.
# S'arrete tout seul quand le conteneur a fini. Journal : ${HANNIBAL_HOME:-$HOME/hannibal}/v2/garde_temperature_train.log
C=hannibal-train; GMAX=84; GOK=74; CMAX=95; COK=85; L=${HANNIBAL_HOME:-$HOME/hannibal}/v2/garde_temperature_train.log
cpu(){ for z in /sys/class/thermal/thermal_zone*/; do [ "$(cat $z/type)" = x86_pkg_temp ] && echo $(( $(cat $z/temp) / 1000 )); done | head -1; }
while [ "$(docker inspect -f '{{.State.Status}}' $C 2>/dev/null)" = running ] || [ "$(docker inspect -f '{{.State.Status}}' $C 2>/dev/null)" = paused ]; do
  g=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader | head -1); c=$(cpu); st=$(docker inspect -f '{{.State.Status}}' $C)
  if [ "$st" = running ] && { [ "$g" -ge $GMAX ] || [ "${c:-0}" -ge $CMAX ]; }; then docker pause $C >/dev/null; echo "$(date '+%F %T') PAUSE gpu=${g}C cpu=${c}C" >> $L; fi
  if [ "$st" = paused ] && [ "$g" -le $GOK ] && [ "${c:-0}" -le $COK ]; then docker unpause $C >/dev/null; echo "$(date '+%F %T') REPRISE gpu=${g}C cpu=${c}C" >> $L; fi
  [ $(( $(date +%s) % 600 )) -lt 30 ] && echo "$(date '+%F %T') ok gpu=${g}C cpu=${c}C etat=$st" >> $L
  sleep 30
done
echo "$(date '+%F %T') fin (conteneur termine)" >> $L
