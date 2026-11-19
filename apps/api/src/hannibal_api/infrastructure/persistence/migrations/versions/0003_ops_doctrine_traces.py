"""Schéma `ops` : traces des questions de doctrine (architecture 1.1.0 § 7).

Revision ID: 0003_ops_doctrine_traces
"""

from alembic import op

from hannibal_api.infrastructure.persistence.database import execute_script

revision = "0003_ops_doctrine_traces"
down_revision = "0002_ops_commands"
branch_labels = None
depends_on = None

UPGRADE = """
CREATE TABLE ops.doctrine_traces (
    id uuid PRIMARY KEY,
    at timestamptz NOT NULL DEFAULT now(),
    actor_id text NOT NULL,
    question text NOT NULL,
    language text NOT NULL CHECK (language IN ('fr', 'en')),
    publication text,
    status text NOT NULL CHECK (status IN ('answered', 'refused')),
    refusal_reason text CHECK (refusal_reason IN ('no_evidence', 'ungrounded_claim', 'unsupported_answer')),
    answer text NOT NULL,
    cited jsonb NOT NULL DEFAULT '[]',
    model text NOT NULL,
    index_version text NOT NULL,
    thresholds jsonb NOT NULL DEFAULT '{}',
    duration_ms integer NOT NULL
);
CREATE INDEX doctrine_traces_at ON ops.doctrine_traces (at);

DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'hannibal_app') THEN
        GRANT SELECT, INSERT ON ops.doctrine_traces TO hannibal_app;
    END IF;
END
$$;
"""

DOWNGRADE = """
DROP TABLE IF EXISTS ops.doctrine_traces;
"""


def upgrade() -> None:
    execute_script(op.get_bind(), UPGRADE)


def downgrade() -> None:
    execute_script(op.get_bind(), DOWNGRADE)
