"""Schéma `ops_read` : vues publiées pour le back-office (Lot 7, règle « un seul écrivain par schéma »).

Le back-office ne lit jamais les tables d'`ops` ; il lit ces vues, qui sont un contrat : une colonne
retirée ou renommée demande une nouvelle vue, pas une modification de celle-ci.

Revision ID: 0004_ops_read_views
"""

from alembic import op

from hannibal_api.infrastructure.persistence.database import execute_script

revision = "0004_ops_read_views"
down_revision = "0003_ops_doctrine_traces"
branch_labels = None
depends_on = None

UPGRADE = """
CREATE SCHEMA IF NOT EXISTS ops_read;

CREATE VIEW ops_read.mission_runs AS
SELECT
    m.id AS mission_id,
    m.scenario_id,
    m.player_ship,
    m.phase,
    m.owner_id,
    m.started_at,
    m.finished_at,
    m.debrief
FROM ops.missions AS m;

DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'hannibal_backoffice') THEN
        GRANT USAGE ON SCHEMA ops_read TO hannibal_backoffice;
        GRANT SELECT ON ops_read.mission_runs TO hannibal_backoffice;
    END IF;
END
$$;
"""

DOWNGRADE = """
DROP VIEW IF EXISTS ops_read.mission_runs;
DROP SCHEMA IF EXISTS ops_read;
"""


def upgrade() -> None:
    execute_script(op.get_bind(), UPGRADE)


def downgrade() -> None:
    execute_script(op.get_bind(), DOWNGRADE)
