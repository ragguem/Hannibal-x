#!/usr/bin/env bash
# Installation sur le serveur du navire, sans Internet, depuis le dossier du paquet (en root).
#   sudo ./install.sh            # installation ou mise à jour
# Prérequis : Docker et le plugin compose, pilote NVIDIA et nvidia-container-toolkit, rsync,
# les fichiers de /etc/hannibal/ (modèle : opt/compose/secrets.example).
set -euo pipefail
cd "$(dirname "$0")"
version=$(cat VERSION)
project=hannibal
compose=(docker compose -p "$project" -f /opt/hannibal/compose/compose.yml --env-file /etc/hannibal/compose.env)

[[ $EUID -eq 0 ]] || { echo "à lancer en root" >&2; exit 1; }
echo "1/7 sommes de contrôle"
sha256sum --quiet -c SHA256SUMS

echo "2/7 secrets"
required=(compose.env postgres.env migrate.env api.env backoffice.env asr.env rerank.env doctrine.env
  sim-bridge.env grafana.env alert.env metrics.token mtp/signals.json)
for file in "${required[@]}"; do
  [[ -f "/etc/hannibal/$file" ]] || { echo "manquant : /etc/hannibal/$file" >&2; exit 1; }
done
chmod 0700 /etc/hannibal && chmod 0600 /etc/hannibal/*.env /etc/hannibal/metrics.token
chmod 0644 /etc/hannibal/mtp/signals.json
mkdir -p /etc/hannibal/certs
grep -q "^HX_VERSION=$version$" /etc/hannibal/compose.env \
  || { echo "HX_VERSION=$version attendu dans /etc/hannibal/compose.env" >&2; exit 1; }

echo "3/7 images"
for archive in images/*.tar.zst; do zstd -dc "$archive" | docker load -q; done

echo "4/7 fichiers d'exploitation"
mkdir -p /opt/hannibal
rsync -a --delete opt/ /opt/hannibal/
chmod 0755 /opt/hannibal/systemd/*.sh /opt/hannibal/backup/*.sh

echo "5/7 modèles (seulement si le volume est vide)"
load_volume() {  # load_volume <volume> <archive> <uid>
  docker volume create "$1" >/dev/null
  docker run --rm --user 0 --network none -v "$1:/dst" -v "$PWD/models:/src:ro" --entrypoint sh \
    "hannibal/api:$version" -c "[ -n \"\$(ls -A /dst)\" ] || { tar -C /dst -xf /src/$2 && chown -R $3:$3 /dst; }"
}
load_volume "${project}_ollama-data" ollama.tar 0
load_volume "${project}_asr-models" asr-models.tar 10001
load_volume "${project}_rerank-models" rerank-models.tar 10001

echo "6/7 base et services"
"${compose[@]}" up -d --wait postgres
for role in hannibal_app hannibal_doctrine; do
  exists=$("${compose[@]}" exec -T postgres sh -c \
    "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -tAc \"SELECT 1 FROM pg_roles WHERE rolname = '$role'\"")
  [[ "$exists" == 1 ]] || { echo "rôle $role absent : le créer (docs/exploitation.md), puis relancer" >&2; exit 1; }
done
"${compose[@]}" --profile deploy run --rm migrate
"${compose[@]}" --profile deploy run --rm backoffice-migrate
"${compose[@]}" up -d --remove-orphans

echo "7/7 minuteries systemd"
cp /opt/hannibal/systemd/*.service /opt/hannibal/systemd/*.timer /etc/systemd/system/
cp /opt/hannibal/backup/*.service /opt/hannibal/backup/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now hannibal-ready.timer hannibal-backup.timer hannibal-restore-test.timer

echo "installé : Hannibal X $version. Contrôle : ${compose[*]} ps ; /opt/hannibal/systemd/check-ready.sh"
