"""Métriques de `GpuGate` : jetons actifs et en attente par classe, durée d'attente d'un jeton."""

from prometheus_client import CollectorRegistry, Gauge, Histogram

from hannibal_api.application.gpu_gate import GpuGate


def expose_gpu_gate(registry: CollectorRegistry, gate: GpuGate) -> None:
    waits = Histogram(
        "gpu_gate_wait_seconds",
        "Attente d'un jeton GpuGate",
        ["kind"],
        registry=registry,
        buckets=(0.01, 0.1, 0.5, 1, 2, 5, 10, 20),
    )
    gate.observe_waits(lambda kind, seconds: waits.labels(kind).observe(seconds))
    tokens = Gauge("gpu_gate_tokens", "Jetons GpuGate", ["kind", "state"], registry=registry)
    tokens.labels("voice", "active").set_function(lambda: gate.snapshot().voice_active)
    tokens.labels("voice", "waiting").set_function(lambda: gate.snapshot().voice_waiting)
    tokens.labels("doctrine", "active").set_function(lambda: gate.snapshot().doctrine_active)
    tokens.labels("doctrine", "waiting").set_function(lambda: gate.snapshot().doctrine_waiting)
