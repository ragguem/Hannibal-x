import time

from dependency_injector import containers, providers

from hannibal_api.application.audit import AuditTrail
from hannibal_api.application.check_readiness import CheckReadiness
from hannibal_api.application.commands import Commands
from hannibal_api.application.dispatch import Dispatcher
from hannibal_api.application.doctrine import ExplainCommand, QueryDoctrine, SearchGlossary
from hannibal_api.application.gpu_gate import GateLimits, GpuGate
from hannibal_api.application.missions import Missions
from hannibal_api.application.voice_orders import VoiceOrders
from hannibal_api.domain.readiness import ProbeState
from hannibal_api.infrastructure.asr import AsrClient, ScriptedTranscriber
from hannibal_api.infrastructure.doctrine import DoctrineClient, SampleDoctrine
from hannibal_api.infrastructure.fleet import InMemoryFleet
from hannibal_api.infrastructure.persistence.commands import PostgresCommandStore
from hannibal_api.infrastructure.persistence.database import create_database_engine
from hannibal_api.infrastructure.persistence.doctrine_traces import PostgresDoctrineTraceStore
from hannibal_api.infrastructure.persistence.journal import PostgresAuditReader, PostgresMissionJournal
from hannibal_api.infrastructure.persistence.memory import (
    InMemoryCommandStore,
    InMemoryDoctrineTraceStore,
    InMemoryMissionJournal,
)
from hannibal_api.infrastructure.probes import FakeProbe, HttpProbe, PostgresProbe
from hannibal_api.infrastructure.recordings import FileVoiceRecordingStore, InMemoryVoiceRecordingStore
from hannibal_api.infrastructure.scenarios import YamlScenarioCatalog
from hannibal_api.infrastructure.sim_bridge import SimBridgeClient
from hannibal_api.infrastructure.simulator import InMemorySimulator
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
        providers.Singleton(
            HttpProbe,
            name="sim-bridge",
            url=settings.provided.sim_bridge_health_url,
            timeout_s=settings.provided.readiness_timeout_s,
            required=True,
        ),
        providers.Singleton(
            HttpProbe,
            name="asr",
            url=settings.provided.asr_health_url,
            timeout_s=settings.provided.readiness_timeout_s,
        ),
        providers.Singleton(
            HttpProbe,
            name="doctrine",
            url=settings.provided.doctrine_health_url,
            timeout_s=settings.provided.readiness_timeout_s,
        ),
    )
    fake_probes = providers.List(
        providers.Singleton(FakeProbe, name="postgres"),
        providers.Singleton(FakeProbe, name="sim-bridge"),
        providers.Singleton(FakeProbe, name="asr", required=False),
        providers.Singleton(FakeProbe, name="doctrine", required=False),
        providers.Singleton(FakeProbe, name="ollama", state=ProbeState.DISABLED, required=False),
    )
    probes = providers.Selector(mode, fake=fake_probes, real=real_probes)

    check_readiness = providers.Singleton(
        CheckReadiness,
        probes=probes,
        timeout_s=settings.provided.readiness_timeout_s,
    )

    clock = providers.Object(time.monotonic)
    sim_bridge = providers.Singleton(
        SimBridgeClient,
        base_url=settings.provided.sim_bridge_base_url,
        token=settings.provided.internal_token_value,
        timeout_s=settings.provided.sim_bridge_timeout_s,
    )
    simulator = providers.Selector(
        mode,
        fake=providers.Singleton(
            InMemorySimulator, origin_lat_lon=settings.provided.simulator_origin_lat_lon, clock=clock
        ),
        real=sim_bridge,
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

    fleet = providers.Selector(mode, fake=providers.Singleton(InMemoryFleet), real=sim_bridge)
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

    gpu_gate = providers.Singleton(
        GpuGate,
        voice=providers.Factory(
            GateLimits,
            active=settings.provided.voice_active,
            waiting=settings.provided.voice_waiting,
            wait_s=settings.provided.voice_wait_s,
        ),
        doctrine=providers.Factory(
            GateLimits,
            active=settings.provided.doctrine_active,
            waiting=settings.provided.doctrine_waiting,
            wait_s=settings.provided.doctrine_wait_s,
        ),
    )
    asr_client = providers.Singleton(
        AsrClient,
        base_url=settings.provided.asr_base_url,
        token=settings.provided.internal_token_value,
        timeout_s=settings.provided.asr_timeout_s,
    )
    transcriber = providers.Selector(
        mode,
        fake=providers.Singleton(ScriptedTranscriber, transcript=settings.provided.scripted_transcript),
        real=asr_client,
    )
    recordings = providers.Selector(
        mode,
        fake=providers.Singleton(InMemoryVoiceRecordingStore),
        real=providers.Singleton(FileVoiceRecordingStore, directory=settings.provided.recordings_dir),
    )
    voice_orders = providers.Singleton(
        VoiceOrders,
        missions=missions,
        commands=commands,
        transcriber=transcriber,
        recordings=recordings,
        journal=journal,
        gate=gpu_gate,
        min_recording_bytes=settings.provided.min_recording_bytes,
        max_recording_bytes=settings.provided.max_recording_bytes,
    )

    doctrine_client = providers.Singleton(
        DoctrineClient,
        base_url=settings.provided.doctrine_base_url,
        token=settings.provided.internal_token_value,
        timeout_s=settings.provided.doctrine_timeout_s,
    )
    doctrine = providers.Selector(mode, fake=providers.Singleton(SampleDoctrine), real=doctrine_client)
    doctrine_traces = providers.Selector(
        mode,
        fake=providers.Singleton(InMemoryDoctrineTraceStore, journal=in_memory_journal),
        real=providers.Singleton(PostgresDoctrineTraceStore, engine=database_engine),
    )
    query_doctrine = providers.Singleton(
        QueryDoctrine, doctrine=doctrine, traces=doctrine_traces, gate=gpu_gate
    )
    search_glossary = providers.Singleton(SearchGlossary, doctrine=doctrine)
    explain_command = providers.Singleton(ExplainCommand, doctrine=doctrine, commands=commands, gate=gpu_gate)
