#!/usr/bin/env bash
# Filet de supervision (toutes les minutes) : /v1/ready par le proxy et l'état de la carte.
# Alerte par HX_ALERT_COMMAND (messagerie du site), même si Prometheus est tombé.
set -euo pipefail
# shellcheck source=/dev/null
source /etc/hannibal/alert.env

alert() {
  # shellcheck disable=SC2086
  $HX_ALERT_COMMAND "hannibal: $1" || logger -t hannibal-alert "$1"
}

cacert=()
if [[ -n "${HX_READY_CACERT:-}" ]]; then
  cacert=(--cacert "$HX_READY_CACERT")
fi

if ! body=$(curl -fsS --max-time 10 "${cacert[@]}" "$HX_READY_URL" 2>&1); then
  alert "/v1/ready en échec : ${body:0:300}"
  exit 1
fi

if command -v nvidia-smi >/dev/null && ! nvidia-smi --query-gpu=name --format=csv,noheader >/dev/null 2>&1; then
  alert "nvidia-smi ne répond pas"
  exit 1
fi
