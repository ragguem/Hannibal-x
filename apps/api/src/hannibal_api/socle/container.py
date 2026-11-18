from dependency_injector import containers, providers

from hannibal_api.application.check_readiness import CheckReadiness
from hannibal_api.domain.readiness import ProbeState
from hannibal_api.infrastructure.probes import FakeProbe, HttpProbe, PostgresProbe
from hannibal_api.socle.settings import AdapterMode, ApiSettings


class Container(containers.DeclarativeContainer):
    settings = providers.Dependency(instance_of=ApiSettings)

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
    probes = providers.Selector(
        providers.Callable(lambda s: AdapterMode(s.adapters).value, settings),
        fake=fake_probes,
        real=real_probes,
    )

    check_readiness = providers.Singleton(
        CheckReadiness,
        probes=probes,
        timeout_s=settings.provided.readiness_timeout_s,
    )
