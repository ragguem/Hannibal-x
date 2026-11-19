#!/usr/bin/env bash
# Test de restauration (mensuel) : la dernière sauvegarde dans une base jetable, puis vérification
# de la chaîne d'audit. Rien n'est écrit dans la base de production.
set -euo pipefail
# shellcheck source=/dev/null
source /etc/hannibal/alert.env

image=${HX_POSTGRES_IMAGE:-pgvector/pgvector:0.8.7-pg17}
name="hannibal-restore-test-$$"

fail() {
  # shellcheck disable=SC2086
  $HX_ALERT_COMMAND "hannibal: test de restauration en échec : $1" || logger -t hannibal-alert "restauration : $1"
  exit 1
}
cleanup() { docker rm -f "$name" >/dev/null 2>&1 || true; }
trap cleanup EXIT

dump=$(ls -1t "$HX_BACKUP_DIR"/pg/hannibal-*.dump 2>/dev/null | head -n 1)
[[ -n "$dump" ]] || fail "aucune sauvegarde dans $HX_BACKUP_DIR/pg"
sha256sum --quiet -c "$dump.sha256" || fail "somme de contrôle invalide pour $dump"

password=$(openssl rand -hex 16)
docker run -d --name "$name" --network none -e POSTGRES_PASSWORD="$password" -e POSTGRES_DB=restore \
  -v "$dump:/restore.dump:ro" "$image" >/dev/null
for _ in $(seq 1 60); do
  docker exec "$name" pg_isready -U postgres -d restore >/dev/null 2>&1 && break
  sleep 1
done

docker exec "$name" pg_restore --no-owner --no-privileges -U postgres -d restore /restore.dump \
  || fail "pg_restore a échoué ($dump)"

result=$(docker exec "$name" psql -U postgres -d restore -tA -F ' ' \
  -c "SELECT checked_events, coalesce(first_broken_seq::text, 'none') FROM ops.verify_audit_chain()") \
  || fail "vérification de la chaîne impossible"
read -r checked broken <<< "$result"
[[ "$broken" == "none" ]] || fail "chaîne d'audit rompue à seq=$broken ($dump)"

date -u +%FT%TZ > "$HX_BACKUP_DIR/last-restore-test"
logger -t hannibal-backup "restauration vérifiée : $dump, $checked événements d'audit, chaîne intacte"
