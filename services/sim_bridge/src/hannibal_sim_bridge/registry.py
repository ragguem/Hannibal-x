"""Registre des manœuvres exécutées : un identifiant de commande n'est enregistré qu'une fois.

Avec un chemin, chaque enregistrement est ajouté à un fichier JSON Lines relu au démarrage : un redémarrage de
`sim-bridge` ne fait pas rejouer une manœuvre déjà reçue.
"""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ManeuverConflict(Exception):
    """Même identifiant, manœuvre différente."""


@dataclass(frozen=True, slots=True)
class RecordedManeuver:
    command_id: str
    maneuver: dict[str, Any]
    recorded_at: datetime


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ManeuverRegistry:
    def __init__(self, path: Path | None = None, clock: Callable[[], datetime] = _utc_now) -> None:
        self._path = path
        self._clock = clock
        self._records: dict[str, RecordedManeuver] = {}
        if path is not None and path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    self._records[row["command_id"]] = RecordedManeuver(
                        row["command_id"], row["maneuver"], datetime.fromisoformat(row["recorded_at"])
                    )

    def get(self, command_id: str) -> RecordedManeuver | None:
        return self._records.get(command_id)

    def record(self, command_id: str, maneuver: Mapping[str, Any]) -> tuple[RecordedManeuver, bool]:
        """Rend l'enregistrement et `True` s'il vient d'être créé, `False` s'il existait déjà."""
        existing = self._records.get(command_id)
        if existing is not None:
            if existing.maneuver != dict(maneuver):
                raise ManeuverConflict(command_id)
            return existing, False
        recorded = RecordedManeuver(command_id, dict(maneuver), self._clock())
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            row = {
                "command_id": command_id,
                "maneuver": recorded.maneuver,
                "recorded_at": recorded.recorded_at.isoformat(),
            }
            with self._path.open("a", encoding="utf-8") as journal:
                journal.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        self._records[command_id] = recorded
        return recorded, True
