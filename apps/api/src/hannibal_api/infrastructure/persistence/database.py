from typing import Any

from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.util import await_only


def to_sqlalchemy_url(dsn: str) -> str:
    """`postgresql://…` (forme partagée avec la sonde asyncpg) → `postgresql+asyncpg://…`."""
    for prefix in ("postgresql://", "postgres://"):
        if dsn.startswith(prefix):
            return "postgresql+asyncpg://" + dsn.removeprefix(prefix)
    return dsn


def create_database_engine(dsn: str | None) -> AsyncEngine | None:
    """Sans URL, pas de moteur : les adaptateurs répondent alors `database_unavailable`."""
    if not dsn:
        return None
    return create_async_engine(to_sqlalchemy_url(dsn), pool_size=5, max_overflow=5, pool_pre_ping=True)


def execute_script(connection: Connection, script: str) -> None:
    """Exécute plusieurs instructions d'un coup (protocole simple d'asyncpg) ; à appeler sous `run_sync`."""
    driver_connection: Any = connection.connection.driver_connection
    await_only(driver_connection.execute(script))
