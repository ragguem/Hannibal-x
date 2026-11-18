#!/usr/bin/env python3
"""Enregistre les réponses du service doctrine actuel (hx2_service_c, port 8774) à une liste de questions.

À lancer sur le serveur. Bibliothèque standard seulement.

    python3 record_doctrine.py --questions questions.jsonl --out /var/lib/hannibal/recordings/doctrine.jsonl

Entrée : une question par ligne, `{"id": "...", "q": "...", "lang": "fr", "classified": false}`.
Sortie : `{"id", "request", "response", "elapsed_s"}` par ligne. Questions et réponses citent les
publications : les deux fichiers restent hors dépôt (voir docs/donnees-hors-depot.md).
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def ask(base: str, body: dict[str, object], timeout: float) -> object:
    request = urllib.request.Request(
        base + "/ask",
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base", default="http://127.0.0.1:8774")
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    questions = [
        json.loads(line) for line in args.questions.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    failures = 0
    with args.out.open("w", encoding="utf-8") as out:
        for item in questions:
            body = {k: v for k, v in item.items() if k != "id"}
            started = time.monotonic()
            try:
                response: object = ask(args.base, body, args.timeout)
            except (urllib.error.URLError, TimeoutError) as exc:
                response, failures = {"error": type(exc).__name__}, failures + 1
            record = {
                "id": item.get("id"),
                "request": body,
                "response": response,
                "elapsed_s": round(time.monotonic() - started, 2),
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            sys.stdout.write(f"{item.get('id')}: {record['elapsed_s']} s\n")
    sys.stdout.write(f"{len(questions)} questions, {failures} échecs, sortie {args.out}\n")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
