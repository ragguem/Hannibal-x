"""Applique les migrations du schéma `ops` : `hx-api-migrate [révision]` (par défaut `head`).

Lancé par le conteneur `migrate` avec le rôle `hannibal_migrator`, avant l'API.
"""

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from hannibal_api.socle.settings import ApiSettings

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "infrastructure" / "persistence" / "migrations"


def alembic_config(database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def upgrade(database_url: str, revision: str = "head") -> None:
    command.upgrade(alembic_config(database_url), revision)


def downgrade(database_url: str, revision: str) -> None:
    command.downgrade(alembic_config(database_url), revision)


def main() -> int:
    database_url = ApiSettings().database_dsn
    if not database_url:
        sys.stderr.write("HX_API_DATABASE_URL n'est pas défini\n")
        return 2
    upgrade(database_url, sys.argv[1] if len(sys.argv) > 1 else "head")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
