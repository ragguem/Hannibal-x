"""Schéma `ops` : commandes soumises à revue et registre persistant des envois (§ 7, § 9).

Revision ID: 0002_ops_commands
"""

from alembic import op

from hannibal_api.infrastructure.persistence.database import execute_script

revision = "0002_ops_commands"
down_revision = "0001_ops_initial"
branch_labels = None
depends_on = None

UPGRADE = """
CREATE TABLE ops.commands (
    id uuid PRIMARY KEY,
    mission_id uuid NOT NULL REFERENCES ops.missions (id),
    parent_id uuid REFERENCES ops.commands (id),
    source text NOT NULL CHECK (source IN ('voice', 'keyboard', 'scenario')),
    text text NOT NULL,
    maneuver jsonb NOT NULL,
    state text NOT NULL CHECK (
        state IN ('awaiting_review', 'rejected', 'dispatching', 'dispatched', 'dispatch_failed')
    ),
    submitted_by text NOT NULL,
    decided_by text,
    decided_at timestamptz,
    dispatched_at timestamptz,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX commands_mission_state ON ops.commands (mission_id, state);

CREATE TABLE ops.command_dispatches (
    command_id uuid PRIMARY KEY REFERENCES ops.commands (id),
    status text NOT NULL CHECK (status IN ('queued', 'in_flight', 'done', 'failed')),
    attempts integer NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    last_attempt_at timestamptz,
    deadline_at timestamptz NOT NULL,
    last_error text,
    queued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX command_dispatches_queued ON ops.command_dispatches (next_attempt_at) WHERE status = 'queued';

DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'hannibal_app') THEN
        GRANT SELECT, INSERT, UPDATE ON ops.commands, ops.command_dispatches TO hannibal_app;
    END IF;
END
$$;
"""

DOWNGRADE = """
DROP TABLE IF EXISTS ops.command_dispatches;
DROP TABLE IF EXISTS ops.commands;
"""


def upgrade() -> None:
    execute_script(op.get_bind(), UPGRADE)


def downgrade() -> None:
    execute_script(op.get_bind(), DOWNGRADE)
