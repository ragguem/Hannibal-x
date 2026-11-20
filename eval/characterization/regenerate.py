"""Régénère `golden/` depuis hannibal_core.

    uv run python eval/characterization/regenerate.py [interpret mtp sim reco hxbridge]

À lancer seulement quand un changement de comportement est voulu ; le diff des goldens
doit être relu, et l'écart décrit dans le README (« Écarts voulus »).
"""

import sys

from golden_harness import GOLDEN, RUNNERS, dump


def main(args: list[str]) -> int:
    names = args or list(RUNNERS)
    GOLDEN.mkdir(parents=True, exist_ok=True)
    for name in names:
        (GOLDEN / f"{name}.json").write_text(dump(RUNNERS[name]()), encoding="utf-8", newline="\n")
        sys.stdout.write(f"golden/{name}.json écrit\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
