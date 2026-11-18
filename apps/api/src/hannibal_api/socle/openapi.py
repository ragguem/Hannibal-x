"""Écrit le contrat HTTP public dans `apps/api/openapi.json` (§ 12 : le schéma est commité).

Le test de dérive échoue si une route change sans régénération : `uv run hx-export-openapi`.
"""

import json
import sys
from pathlib import Path

from hannibal_api.socle.main import create_app
from hannibal_api.socle.settings import AdapterMode, ApiSettings

OPENAPI_FILE = Path(__file__).resolve().parents[3] / "openapi.json"


def render() -> str:
    app = create_app(ApiSettings(adapters=AdapterMode.FAKE, mission_runner_period_s=0))
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> int:
    OPENAPI_FILE.write_text(render(), encoding="utf-8", newline="\n")
    sys.stdout.write(f"contrat écrit dans {OPENAPI_FILE}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
