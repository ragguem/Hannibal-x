"""Régénère `golden/` depuis l'ancien code.

    uv run python eval/characterization/regenerate.py [interpret mtp sim reco hxbridge]

À lancer seulement quand un changement de comportement de l'ancien code est voulu ;
le diff des goldens doit être relu dans la revue.
"""

import sys

from legacy_harness import GOLDEN, RUNNERS, dump, golden_path


def main(names: list[str]) -> int:
    GOLDEN.mkdir(exist_ok=True)
    for name in names or list(RUNNERS):
        golden_path(name).write_text(dump(RUNNERS[name]()), encoding="utf-8", newline="\n")
        sys.stdout.write(f"golden/{name}.json écrit\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
