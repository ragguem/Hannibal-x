"""Schéma `ops` 1.0.0 : missions, registre d'audit chaîné, boîte d'envoi des faits métier.

Revision ID: 0001_ops_initial
"""

from alembic import op

from hannibal_api.infrastructure.persistence.database import execute_script

revision = "0001_ops_initial"
down_revision = None
branch_labels = ("ops-1.0.0",)
depends_on = None

AUDIT_LOCK_KEY = 7243001

UPGRADE = f"""
CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE ops.missions (
    id uuid PRIMARY KEY,
    scenario_id text NOT NULL,
    player_ship text NOT NULL,
    phase text NOT NULL CHECK (phase IN ('running', 'finished', 'interrupted')),
    owner_id text NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    debrief jsonb
);
CREATE UNIQUE INDEX missions_single_running ON ops.missions ((true)) WHERE phase = 'running';

CREATE TABLE ops.audit_events (
    seq bigint PRIMARY KEY,
    at timestamptz NOT NULL,
    actor_id text,
    mission_id uuid,
    command_id uuid,
    event text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    prev_hash bytea,
    hash bytea NOT NULL UNIQUE
);
CREATE INDEX audit_events_mission_at ON ops.audit_events (mission_id, at);

CREATE TABLE ops.integration_outbox (
    id uuid PRIMARY KEY,
    specversion varchar(8) NOT NULL DEFAULT '1.0',
    type text NOT NULL,
    source text NOT NULL,
    subject text,
    time timestamptz NOT NULL DEFAULT now(),
    data jsonb NOT NULL,
    published_at timestamptz
);
CREATE INDEX integration_outbox_unpublished ON ops.integration_outbox (time) WHERE published_at IS NULL;

-- Forme canonique d'une ligne d'audit : jsonb (clés ordonnées par PostgreSQL), instant UTC à la microseconde.
CREATE FUNCTION ops.audit_canonical_form(
    seq bigint, at timestamptz, actor_id text, mission_id uuid, command_id uuid, event text, payload jsonb
) RETURNS bytea LANGUAGE sql STABLE AS $$
    SELECT convert_to(
        jsonb_build_object(
            'seq', seq,
            'at', to_char(at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
            'actor_id', actor_id,
            'mission_id', mission_id,
            'command_id', command_id,
            'event', event,
            'payload', payload
        )::text,
        'UTF8'
    )
$$;

CREATE FUNCTION ops.audit_link_hash(prev_hash bytea, canonical_form bytea) RETURNS bytea
LANGUAGE sql IMMUTABLE AS $$
    SELECT sha256(coalesce(prev_hash, ''::bytea) || canonical_form)
$$;

CREATE FUNCTION ops.audit_chain() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, ops AS $$
DECLARE
    last_seq bigint;
    last_hash bytea;
BEGIN
    PERFORM pg_advisory_xact_lock({AUDIT_LOCK_KEY});
    SELECT a.seq, a.hash INTO last_seq, last_hash FROM ops.audit_events a ORDER BY a.seq DESC LIMIT 1;
    NEW.seq := coalesce(last_seq, 0) + 1;
    NEW.prev_hash := last_hash;
    NEW.at := now();
    NEW.payload := coalesce(NEW.payload, '{{}}'::jsonb);
    NEW.hash := ops.audit_link_hash(
        last_hash,
        ops.audit_canonical_form(
            NEW.seq, NEW.at, NEW.actor_id, NEW.mission_id, NEW.command_id, NEW.event, NEW.payload
        )
    );
    RETURN NEW;
END
$$;
CREATE TRIGGER audit_events_chain BEFORE INSERT ON ops.audit_events
    FOR EACH ROW EXECUTE FUNCTION ops.audit_chain();

CREATE FUNCTION ops.audit_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' AND current_user = 'hannibal_audit_archiver' THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'ops.audit_events est en ajout seul (%)', TG_OP USING ERRCODE = 'insufficient_privilege';
END
$$;
CREATE TRIGGER audit_events_append_only BEFORE UPDATE OR DELETE ON ops.audit_events
    FOR EACH ROW EXECUTE FUNCTION ops.audit_append_only();
CREATE TRIGGER audit_events_no_truncate BEFORE TRUNCATE ON ops.audit_events
    FOR EACH STATEMENT EXECUTE FUNCTION ops.audit_append_only();

CREATE FUNCTION ops.audit_head() RETURNS TABLE (seq bigint, hash bytea) LANGUAGE sql STABLE AS $$
    SELECT a.seq, a.hash FROM ops.audit_events a ORDER BY a.seq DESC LIMIT 1
$$;

-- Recalcule la chaîne et renvoie la première ligne en rupture (modifiée, insérée ou retirée après coup).
CREATE FUNCTION ops.verify_audit_chain(from_seq bigint DEFAULT 1, to_seq bigint DEFAULT NULL)
RETURNS TABLE (checked_events bigint, first_broken_seq bigint) LANGUAGE plpgsql STABLE AS $$
DECLARE
    row_ ops.audit_events%ROWTYPE;
    expected_seq bigint := from_seq;
    expected_prev bytea;
    first_row boolean := true;
BEGIN
    checked_events := 0;
    first_broken_seq := NULL;
    SELECT a.hash INTO expected_prev FROM ops.audit_events a WHERE a.seq = from_seq - 1;
    FOR row_ IN
        SELECT * FROM ops.audit_events a
        WHERE a.seq >= from_seq AND (to_seq IS NULL OR a.seq <= to_seq)
        ORDER BY a.seq
    LOOP
        IF row_.seq <> expected_seq
            OR (row_.prev_hash IS DISTINCT FROM expected_prev
                AND NOT (first_row AND from_seq > 1 AND expected_prev IS NULL))
            OR row_.hash <> ops.audit_link_hash(
                row_.prev_hash,
                ops.audit_canonical_form(
                    row_.seq, row_.at, row_.actor_id, row_.mission_id,
                    row_.command_id, row_.event, row_.payload
                )
            )
        THEN
            first_broken_seq := row_.seq;
            RETURN NEXT;
            RETURN;
        END IF;
        checked_events := checked_events + 1;
        expected_prev := row_.hash;
        expected_seq := row_.seq + 1;
        first_row := false;
    END LOOP;
    RETURN NEXT;
END
$$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hannibal_app') THEN
        GRANT USAGE ON SCHEMA ops TO hannibal_app;
        GRANT SELECT, INSERT, UPDATE ON ops.missions, ops.integration_outbox TO hannibal_app;
        GRANT SELECT ON ops.audit_events TO hannibal_app;
        GRANT INSERT (actor_id, mission_id, command_id, event, payload) ON ops.audit_events TO hannibal_app;
        GRANT EXECUTE ON FUNCTION ops.audit_head(), ops.verify_audit_chain(bigint, bigint) TO hannibal_app;
    END IF;
END
$$;
"""  # noqa: S608 (seule interpolation : la constante entière AUDIT_LOCK_KEY)

DOWNGRADE = """
DROP FUNCTION IF EXISTS ops.verify_audit_chain(bigint, bigint);
DROP FUNCTION IF EXISTS ops.audit_head();
DROP TABLE IF EXISTS ops.audit_events;
DROP FUNCTION IF EXISTS ops.audit_append_only();
DROP FUNCTION IF EXISTS ops.audit_chain();
DROP FUNCTION IF EXISTS ops.audit_link_hash(bytea, bytea);
DROP FUNCTION IF EXISTS ops.audit_canonical_form(bigint, timestamptz, text, uuid, uuid, text, jsonb);
DROP TABLE IF EXISTS ops.integration_outbox;
DROP TABLE IF EXISTS ops.missions;
"""


def upgrade() -> None:
    execute_script(op.get_bind(), UPGRADE)


def downgrade() -> None:
    execute_script(op.get_bind(), DOWNGRADE)
