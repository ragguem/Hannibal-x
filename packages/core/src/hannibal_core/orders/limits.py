"""Limite de vitesse unique pour tous les chemins d'ordre (clavier, signal, voix)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SpeedLimits:
    """Bornes en nœuds. Un ordre hors bornes est ramené à la borne, avec une note pour l'opérateur."""

    min_kn: int = 3
    max_kn: int = 28

    def __post_init__(self) -> None:
        if not 0 < self.min_kn <= self.max_kn:
            raise ValueError(f"bornes de vitesse invalides : {self.min_kn} à {self.max_kn}")

    def clamp(self, kn: float) -> tuple[int, str | None]:
        k = max(self.min_kn, min(self.max_kn, round(kn)))
        if k != kn:
            return k, f"Vitesse ramenée à {k} nœuds (limites du simulateur : {self.min_kn} à {self.max_kn})."
        return k, None


DEFAULT_SPEED = SpeedLimits()
