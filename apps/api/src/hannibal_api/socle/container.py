import time

from dependency_injector import containers, providers

from hannibal_api.application.audit import AuditTrail
from hannibal_api.application.check_readiness import CheckReadiness
from hannibal_api.application.commands import Commands
from hannibal_api.application.dispatch import Dispatcher
from hannibal_api.application.missions import Missions
from hannibal_api.domain.readiness import ProbeState
from hannibal_api.infrastructure.fleet import InMemoryFleet, UnavailableFleet
from hannibal_api.infrastructure.persistence.commands import PostgresCommandStore
from hannibal_api.infrastructure.persistence.database import create_database_engine
from hannibal_api.infrastructure.persistence.journal import PostgresAuditReader, PostgresMissionJournal
from hannibal_api.infrastructure.persistence.memory import InMemoryCommandStore, InMemoryMissionJournal
from hannibal_api.infrastructure.probes import FakeProbe, HttpProbe, PostgresProbe
from hannibal_api.infrastructure.scenarios import YamlScenarioCatalog
from hannibal_api.infrastructure.simulator import InMemorySimulator, UnavailableSimulator
from hannibal_api.socle.settings import AdapterMode, ApiSettings


class Container(containers.DeclarativeContainer):
    settings = providers.Dependency(instance_of=ApiSettings)
    mode = providers.Callable(lambda s: AdapterMode(s.adapters).value, settings)

    real_probes = providers.List(
        providers.Singleton(
            PostgresProbe,
            dsn=settings.provided.database_dsn,
            timeout_s=settings.provided.readiness_timeout_s,
        ),
        providers.Singleton(
            HttpProbe,
            name="ollama",
            url=settings.provided.ollama_health_url,
            timeout_s=settings.provided.readiness_timeout_s,
        ),
    )
    fake_probes = providers.List(
        providers.Singleton(FakeProbe, name="postgres"),
        providers.Singleton(FakeProbe, name="ollama", state=ProbeState.DISABLED, required=False),
    )
    probes = providers.Selector(mode, fake=fake_probes, real=real_probes)

    check_readiness = providers.Singleton(
        CheckReadiness,
        probes=probes,
        timeout_s=settings.provided.readiness_timeout_s,
    )

    clock = providers.Object(time.monotonic)
    simulator = providers.Selector(
        mode,
        fake=providers.Singleton(
            InMemorySimulator, origin_lat_lon=settings.provided.simulator_origin_lat_lon, clock=clock
        ),
        real=providers.Singleton(UnavailableSimulator),
    )
    scenarios = providers.Singleton(YamlScenarioCatalog, directory=settings.provided.scenarios_dir)

    database_engine = providers.Singleton(create_database_engine, dsn=settings.provided.database_dsn)
    in_memory_journal = providers.Singleton(InMemoryMissionJournal)
    journal = providers.Selector(
        mode,
        fake=in_memory_journal,
        real=providers.Singleton(PostgresMissionJournal, engine=database_engine),
    )
    audit_reader = providers.Selector(
        mode,
        fake=in_memory_journal,
        real=providers.Singleton(PostgresAuditReader, engine=database_engine),
    )
    audit_trail = providers.Singleton(AuditTrail, reader=audit_reader)

    missions = providers.Singleton(
        Missions,
        catalog=scenarios,
        simulator=simulator,
        journal=journal,
        clock=clock,
        runner_period_s=settings.provided.mission_runner_period_s,
    )

    fleet = providers.Selector(
        mode, fake=providers.Singleton(InMemoryFleet), real=providers.Singleton(UnavailableFleet)
    )
    command_store = providers.Selector(
        mode,
        fake=providers.Singleton(InMemoryCommandStore, journal=in_memory_journal, clock=clock),
        real=providers.Singleton(PostgresCommandStore, engine=database_engine),
    )
    dispatcher = providers.Singleton(
        Dispatcher,
        store=command_store,
        fleet=fleet,
        missions=missions,
        max_attempts=settings.provided.dispatch_max_attempts,
        attempt_timeout_s=settings.provided.dispatch_attempt_timeout_s,
        poll_period_s=settings.provided.dispatch_poll_period_s,
    )
    commands = providers.Singleton(
        Commands,
        missions=missions,
        store=command_store,
        wake_dispatcher=dispatcher.provided.wake,
        validity_s=settings.provided.command_validity_s,
    )
