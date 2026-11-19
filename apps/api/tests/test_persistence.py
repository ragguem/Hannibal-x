"""Schéma `ops` sur un vrai PostgreSQL : migrations, chaînage de l'audit, adaptateurs.

    HX_TEST_DATABASE_URL=postgresql://hannibal:…@127.0.0.1:55432/hannibal_test uv run pytest -m postgres

La base est vidée (retour à la révision `base`) avant chaque test : n'utiliser qu'une base jetable.
"""

import os
from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from hannibal_api.domain.audit import AuditEntry, AuditEvent, FactType, MissionOutcome
from hannibal_api.domain.commands import Command, CommandDecision, CommandState
from hannibal_api.infrastructure.persistence.commands import PostgresCommandStore
from hannibal_api.infrastructure.persistence.database import create_database_engine
from hannibal_api.infrastructure.persistence.journal import PostgresAuditReader, PostgresMissionJournal
from hannibal_api.infrastructure.simulator import InMemorySimulator
from hannibal_api.socle.container import Container
from hannibal_api.socle.main import create_app
from hannibal_api.socle.migrate import downgrade, upgrade
from hannibal_api.socle.settings import AdapterMode, ApiSettings

pytestmark = pytest.mark.postgres

DATABASE_URL = os.environ.get("HX_TEST_DATABASE_URL")
MISSION_ID = "6f1c1a52-2f4e-4d39-9a0e-1b4ad7c0e001"
COMMAND_IDS = ("6f1c1a52-2f4e-4d39-9a0e-1b4ad7c0c001", "6f1c1a52-2f4e-4d39-9a0e-1b4ad7c0c002")


@pytest.fixture
def migrated_database() -> str:
    if not DATABASE_URL:
        pytest.skip("HX_TEST_DATABASE_URL non défini (base PostgreSQL jetable)")
    downgrade(DATABASE_URL, "base")
    upgrade(DATABASE_URL)
    return DATABASE_URL


@pytest.fixture
async def engine(migrated_database: str) -> AsyncIterator[AsyncEngine]:
    database_engine = create_database_engine(migrated_database)
    assert database_engine is not None
    yield database_engine
    await database_engine.dispose()


def started_entry(mission_id: str = MISSION_ID) -> AuditEntry:
    return AuditEntry(
        AuditEvent.MISSION_STARTED, "alice", mission_id, {"scenario_id": "s1"}, FactType.MISSION_STARTED
    )


async def record_three_events(engine: AsyncEngine) -> None:
    journal = PostgresMissionJournal(engine)
    await journal.mission_started(MISSION_ID, "s1", "hannibal", "alice", started_entry())
    await journal.record(AuditEntry(AuditEvent.HELM, "alice", MISSION_ID, {"course_deg": 90.0}))
    await journal.mission_finished(
        MISSION_ID,
        MissionOutcome.FINISHED,
        {"score": 2},
        AuditEntry(
            AuditEvent.MISSION_FINISHED, None, MISSION_ID, {"outcome": "finished"}, FactType.MISSION_FINISHED
        ),
    )


async def test_journal_writes_mission_audit_and_facts(engine: AsyncEngine) -> None:
    await record_three_events(engine)
    reader = PostgresAuditReader(engine)

    records = await reader.read(MISSION_ID, after_seq=0, limit=10)
    assert [(r.seq, r.event, r.actor_id) for r in records] == [
        (1, "mission_started", "alice"),
        (2, "helm", "alice"),
        (3, "mission_finished", None),
    ]
    assert (await reader.read(None, after_seq=2, limit=10))[0].seq == 3
    verification = await reader.verify()
    assert verification.intact
    assert (verification.checked_events, verification.head_seq) == (3, 3)

    async with engine.connect() as connection:
        phase, debrief = (await connection.execute(text("SELECT phase, debrief FROM ops.missions"))).one()
        facts = (
            await connection.execute(text("SELECT type FROM ops.integration_outbox ORDER BY time"))
        ).scalars()
        chained = (
            await connection.execute(
                text(
                    "SELECT count(*) FROM ops.audit_events a JOIN ops.audit_events p ON a.prev_hash = p.hash"
                )
            )
        ).scalar_one()
    assert (phase, debrief) == ("finished", {"score": 2})
    assert sorted(facts) == ["hx.mission.finished.v1", "hx.mission.started.v1"]
    assert chained == 2


async def test_audit_is_append_only(engine: AsyncEngine) -> None:
    await record_three_events(engine)
    for statement in (
        "UPDATE ops.audit_events SET payload = '{}' WHERE seq = 2",
        "DELETE FROM ops.audit_events WHERE seq = 2",
        "TRUNCATE ops.audit_events",
    ):
        with pytest.raises(DBAPIError, match="ajout seul"):
            async with engine.begin() as connection:
                await connection.execute(text(statement))


@pytest.mark.parametrize(
    ("tampering", "first_broken_seq"),
    [
        ("UPDATE ops.audit_events SET payload = '{\"course_deg\": 180}' WHERE seq = 2", 2),
        ("DELETE FROM ops.audit_events WHERE seq = 2", 3),
    ],
)
async def test_tampering_breaks_the_chain(engine: AsyncEngine, tampering: str, first_broken_seq: int) -> None:
    await record_three_events(engine)
    async with engine.begin() as connection:
        await connection.execute(
            text("ALTER TABLE ops.audit_events DISABLE TRIGGER audit_events_append_only")
        )
        await connection.execute(text(tampering))
        await connection.execute(text("ALTER TABLE ops.audit_events ENABLE TRIGGER audit_events_append_only"))

    verification = await PostgresAuditReader(engine).verify()
    assert verification.first_broken_seq == first_broken_seq
    assert not verification.intact


async def test_single_running_mission_and_restart_recovery(engine: AsyncEngine) -> None:
    journal = PostgresMissionJournal(engine)
    await journal.mission_started(MISSION_ID, "s1", "hannibal", "alice", started_entry())
    other_mission = "6f1c1a52-2f4e-4d39-9a0e-1b4ad7c0e002"
    with pytest.raises(Exception, match="déjà en cours"):
        await journal.mission_started(other_mission, "s1", "alfa", "bob", started_entry(other_mission))

    assert await journal.interrupt_unfinished() == [MISSION_ID]
    assert await journal.interrupt_unfinished() == []
    last = (await PostgresAuditReader(engine).read(MISSION_ID, after_seq=0, limit=10))[-1]
    assert (last.event, last.payload["reason"]) == ("mission_finished", "api_restarted")
    assert (await PostgresAuditReader(engine).verify()).intact


def review_command(command_id: str) -> Command:
    return Command(
        id=command_id,
        mission_id=MISSION_ID,
        text="ALL SHIPS TURN 30 STBD",
        maneuver={"to": ["TOUS"], "orders": [], "en": "ALL SHIPS TURN 30 STBD", "fr": "Tous : 30 à droite"},
        state=CommandState.AWAITING_REVIEW,
        submitted_by="alice",
    )


def command_entry(event: AuditEvent, command_id: str) -> AuditEntry:
    return AuditEntry(event, "bob", MISSION_ID, {}, command_id=command_id)


async def test_command_store_queues_retries_and_dispatches(engine: AsyncEngine) -> None:
    await PostgresMissionJournal(engine).mission_started(
        MISSION_ID, "s1", "hannibal", "alice", started_entry()
    )
    store = PostgresCommandStore(engine)
    first, second = COMMAND_IDS
    for command_id in COMMAND_IDS:
        await store.create(
            review_command(command_id), [command_entry(AuditEvent.AWAITING_REVIEW, command_id)]
        )

    approve = (CommandState.AWAITING_REVIEW, CommandDecision.APPROVE, "bob")
    decided = await store.decide(first, *approve, 30, command_entry(AuditEvent.APPROVED, first))
    assert decided is not None
    assert (decided.state, decided.decided_by) == (CommandState.DISPATCHING, "bob")
    assert await store.decide(first, *approve, 30, command_entry(AuditEvent.APPROVED, first)) is None
    await store.decide(second, *approve, 0, command_entry(AuditEvent.APPROVED, second))

    claimed = await store.claim_next()
    assert claimed is not None
    assert (claimed.command_id, claimed.attempts, claimed.expired) == (first, 1, False)
    assert [dispatch.command_id for dispatch in await store.in_flight()] == [first]
    await store.retry_later(
        first, 0, "sim-bridge injoignable", command_entry(AuditEvent.DISPATCH_RETRY, first)
    )

    again = await store.claim_next()
    assert again is not None
    assert (again.command_id, again.attempts) == (first, 2)
    await store.mark_dispatched(first, command_entry(AuditEvent.SIMULATOR_DISPATCHED, first))

    expired = await store.claim_next()
    assert expired is not None
    assert (expired.command_id, expired.expired) == (second, True)
    await store.mark_failed(second, "deadline_passed", command_entry(AuditEvent.DISPATCH_FAILED, second))
    retry = (CommandState.DISPATCH_FAILED, CommandDecision.RETRY, "bob")
    assert await store.decide(second, *retry, 30, command_entry(AuditEvent.APPROVED, second)) is None
    assert await store.claim_next() is None

    dispatched = await store.get(first)
    assert dispatched is not None
    assert dispatched.state is CommandState.DISPATCHED
    failed = await store.get(second)
    assert failed is not None
    assert (failed.state, failed.last_error) == (CommandState.DISPATCH_FAILED, "deadline_passed")
    reader = PostgresAuditReader(engine)
    events = [(r.event, r.command_id) for r in await reader.read(MISSION_ID, 0, 50) if r.command_id == first]
    assert [event for event, _ in events] == [
        "awaiting_review",
        "approved",
        "dispatch_retry",
        "simulator_dispatched",
    ]
    assert (await reader.verify()).intact


def test_api_records_a_mission_in_postgres(migrated_database: str) -> None:
    settings = ApiSettings(  # type: ignore[call-arg]
        adapters=AdapterMode.REAL, database_url=migrated_database, log_json=True, mission_runner_period_s=0
    )
    container = Container(settings=settings)
    container.simulator.override(InMemorySimulator(settings.simulator_origin_lat_lon))
    with TestClient(create_app(settings, container)) as client:
        headers = {"X-Hx-User": "alice"}
        body = {"scenario_id": "contact_inconnu", "player_ship": "hannibal"}
        mission_id = client.post("/v1/missions", json=body, headers=headers).json()["id"]
        client.post(
            f"/v1/missions/{mission_id}/orders", json={"text": "ALL SHIPS TURN 30 STBD"}, headers=headers
        )
        assert client.delete(f"/v1/missions/{mission_id}", headers=headers).status_code == 204

        page = client.get("/v1/audit", params={"mission_id": mission_id}).json()
        assert [(e["event"], e["actor_id"]) for e in page["events"]] == [
            ("mission_started", "alice"),
            ("approved", "alice"),
            ("mission_finished", "alice"),
        ]
        assert page["events"][2]["payload"]["outcome"] == "interrupted"
        assert client.get("/v1/audit/integrity").json() == {
            "intact": True,
            "checked_events": 3,
            "first_broken_seq": None,
            "head_seq": 3,
        }
