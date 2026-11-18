from pathlib import Path
from typing import Any

import yaml
from hannibal_core.scenario import load


class YamlScenarioCatalog:
    """Lit et valide tous les `*.yaml` au démarrage : un scénario invalide empêche l'API de démarrer."""

    def __init__(self, directory: Path) -> None:
        self._by_id: dict[str, dict[str, Any]] = {}
        for path in sorted(directory.glob("*.yaml")):
            sc = load(yaml.safe_load(path.read_text(encoding="utf-8")))
            self._by_id[sc["id"]] = sc

    def all(self) -> list[dict[str, Any]]:
        return list(self._by_id.values())

    def get(self, scenario_id: str) -> dict[str, Any] | None:
        return self._by_id.get(scenario_id)
