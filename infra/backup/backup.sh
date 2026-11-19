#!/usr/bin/env bash
# Sauvegarde nocturne : base (pg_dump, format custom) et audio des ordres vers le disque du site.
# Les volumes Docker ne sont pas une sauvegarde. Garde HX_BACKUP_KEEP_DAYS jours (14 par défaut).
set -euo pipefail
# shellcheck source=/dev/null
source /etc/hannibal/alert.env

project=${HX_COMPOSE_PROJECT:-hannibal}
keep_days=${HX_BACKUP_KEEP_DAYS:-14}
stamp=$(date -u +%Y%m%dT%H%M%SZ)
umask 077
mkdir -p "$HX_BACKUP_DIR/pg" "$HX_BACKUP_DIR/recordings"

fail() {
  # shellcheck disable=SC2086
  $HX_ALERT_COMMAND "hannibal: sauvegarde en échec : $1" || logger -t hannibal-alert "sauvegarde : $1"
  exit 1
}
trap 'fail "ligne $LINENO"' ERR

postgres=$(docker ps -q --filter "label=com.docker.compose.project=$project" \
  --filter "label=com.docker.compose.service=postgres")
[[ -n "$postgres" ]] || fail "conteneur postgres introuvable"

dump="$HX_BACKUP_DIR/pg/hannibal-$stamp.dump"
docker exec "$postgres" sh -c 'pg_dump -Fc --no-owner --no-privileges -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > "$dump.partial"
mv "$dump.partial" "$dump"
sha256sum "$dump" > "$dump.sha256"

recordings=$(docker volume inspect -f '{{ .Mountpoint }}' "${project}_recordings")
rsync -a "$recordings/" "$HX_BACKUP_DIR/recordings/"

find "$HX_BACKUP_DIR/pg" -name 'hannibal-*.dump*' -mtime "+$keep_days" -delete
date -u +%FT%TZ > "$HX_BACKUP_DIR/last-backup"
logger -t hannibal-backup "sauvegarde faite : $dump"
