import time

from dependency_injector import containers, providers

from hannibal_api.application.check_readiness import CheckReadiness
from hannibal_api.application.missions import Missions
from hannibal_api.domain.readiness import ProbeState
from hannibal_api.infrastructure.probes import FakeProbe, HttpProbe, PostgresProbe
from hannibal_api.infrastructure.scenarios import YamlScenarioCatalog
from hannibal_api.infrastructure.simulator import FakeSimulator, UnavailableSimulator
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
        fake=providers.Singleton(FakeSimulator, origin=settings.provided.sim_origin, clock=clock),
        real=providers.Singleton(UnavailableSimulator),
    )
    scenarios = providers.Singleton(YamlScenarioCatalog, directory=settings.provided.scenarios_dir)
    missions = providers.Singleton(
        Missions,
        catalog=scenarios,
        simulator=simulator,
        clock=clock,
        tick_s=settings.provided.mission_tick_s,
    )
