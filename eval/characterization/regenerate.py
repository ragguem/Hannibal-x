"""Régénère `golden/` depuis l'ancien code, ou `golden/core/` depuis le cœur.

    uv run python eval/characterization/regenerate.py [interpret mtp sim reco hxbridge]
    uv run python eval/characterization/regenerate.py --core mtp

À lancer seulement quand un changement de comportement est voulu ; le diff des goldens
doit être relu, et tout écart du cœur décrit dans le README (« Écarts voulus »).
"""

import sys

from legacy_harness import GOLDEN, RUNNERS, dump


def main(args: list[str]) -> int:
    core = "--core" in args
    names = [a for a in args if a != "--core"] or list(RUNNERS)
    target = GOLDEN / "core" if core else GOLDEN
    target.mkdir(parents=True, exist_ok=True)
    for name in names:
        output = RUNNERS[name]("core" if core else "legacy")
        (target / f"{name}.json").write_text(dump(output), encoding="utf-8", newline="\n")
        sys.stdout.write(f"{target.relative_to(GOLDEN.parent).as_posix()}/{name}.json écrit\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
