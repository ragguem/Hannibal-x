"""Tables du schéma `ops` vues par l'API. Le DDL est dans les migrations Alembic, pas ici."""

from sqlalchemy import Column, DateTime, MetaData, String, Table, Text
from sqlalchemy.dialects.postgresql import BIGINT, BYTEA, JSONB, UUID

metadata = MetaData(schema="ops")

missions = Table(
    "missions",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("scenario_id", Text, nullable=False),
    Column("player_ship", Text, nullable=False),
    Column("phase", Text, nullable=False),
    Column("owner_id", Text, nullable=False),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("debrief", JSONB),
)

audit_events = Table(
    "audit_events",
    metadata,
    Column("seq", BIGINT, primary_key=True),
    Column("at", DateTime(timezone=True)),
    Column("actor_id", Text),
    Column("mission_id", UUID(as_uuid=False)),
    Column("command_id", UUID(as_uuid=False)),
    Column("event", Text, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("prev_hash", BYTEA),
    Column("hash", BYTEA),
)

integration_outbox = Table(
    "integration_outbox",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("specversion", String(8), nullable=False),
    Column("type", Text, nullable=False),
    Column("source", Text, nullable=False),
    Column("subject", Text),
    Column("time", DateTime(timezone=True)),
    Column("data", JSONB, nullable=False),
    Column("published_at", DateTime(timezone=True)),
)
