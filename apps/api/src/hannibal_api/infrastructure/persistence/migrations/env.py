"""Environnement Alembic du schéma `ops`. Lancé par `hx-api-migrate`, jamais par l'API en marche."""

import asyncio

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from hannibal_api.infrastructure.persistence.database import to_sqlalchemy_url

VERSION_TABLE_SCHEMA = "ops"


def _run(connection: Connection) -> None:
    connection.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {VERSION_TABLE_SCHEMA}")
    context.configure(
        connection=connection,
        version_table_schema=VERSION_TABLE_SCHEMA,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_online() -> None:
    url = context.config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("sqlalchemy.url absent : définir HX_API_DATABASE_URL")
    engine = create_async_engine(to_sqlalchemy_url(url))
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_run)
    finally:
        await engine.dispose()


asyncio.run(_run_online())
