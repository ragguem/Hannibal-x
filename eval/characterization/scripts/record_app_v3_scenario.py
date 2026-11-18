#!/usr/bin/env python3
"""Enregistre un scénario joué par l'ancien serveur (legacy/app_v3) : un état JSON par ligne.

À lancer sur le serveur de démonstration, à côté de l'ancien serveur (port 8773 par défaut).
Bibliothèque standard seulement.

    python3 record_app_v3_scenario.py --scenario transit_colonne --seconds 300 \
        --out /var/lib/hannibal/recordings/transit_colonne.jsonl

L'enregistrement contient les messages échangés pendant le scénario : il reste hors dépôt
(voir docs/donnees-hors-depot.md). Il sert de référence pour comparer le nouveau moteur de scénario.
"""

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path


def call(base: str, path: str, body: dict[str, object] | None = None, timeout: float = 10.0) -> object:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        base + path,
        data=data,
        method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base", default="http://127.0.0.1:8773")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--player", default="hannibal")
    parser.add_argument("--auto", action="store_true", help="active le pilote automatique du scénario")
    parser.add_argument("--seconds", type=float, default=300.0)
    parser.add_argument("--period", type=float, default=0.5, help="période d'échantillonnage en secondes")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--no-stop", action="store_true", help="laisse le scénario tourner à la fin")
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    call(args.base, "/api/start", {"scenario": args.scenario, "player": args.player, "auto": args.auto})
    started = time.monotonic()
    samples = 0
    try:
        with args.out.open("w", encoding="utf-8") as out:
            meta = {
                "scenario": args.scenario,
                "player": args.player,
                "auto": args.auto,
                "period_s": args.period,
            }
            out.write(json.dumps({"meta": meta}, ensure_ascii=False) + "\n")
            while (elapsed := time.monotonic() - started) < args.seconds:
                state = call(args.base, "/api/state")
                out.write(json.dumps({"t": round(elapsed, 3), "state": state}, ensure_ascii=False) + "\n")
                samples += 1
                time.sleep(max(0.0, args.period - (time.monotonic() - started - elapsed)))
    finally:
        if not args.no_stop:
            call(args.base, "/api/stop", {})
    sys.stdout.write(f"{samples} états écrits dans {args.out}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
