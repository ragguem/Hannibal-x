"""Recette de l'assistant de doctrine (Lot 5) : précision, pièges refusés, latence médiane.

Le jeu de questions est hors dépôt (une ligne JSON par question) :
    {"id": "q001", "question": "...", "language": "fr", "publication": "...", "pdf_pages": [12, 13]}
    {"id": "t001", "question": "...", "trap": true}
Une question est juste si la réponse cite la publication attendue (et l'une des pages, si elles sont
données) ; un piège est réussi s'il est refusé. Bibliothèque standard seulement, pour tourner sur le serveur :

    python eval/doctrine/doctrine_eval.py /chemin/hors-depot/doctrine_testset.jsonl --url http://127.0.0.1:8400
"""

import argparse
import json
import statistics
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MIN_ACCURACY = 0.94
MAX_MEDIAN_S = 7.5


@dataclass(frozen=True)
class Outcome:
    case_id: str
    trap: bool
    passed: bool
    seconds: float


def judge(case: dict[str, Any], response: dict[str, Any]) -> bool:
    if case.get("trap"):
        return response.get("status") == "refused"
    if response.get("status") != "answered":
        return False
    pages = set(case.get("pdf_pages") or [])
    return any(
        c.get("publication") == case["publication"] and (not pages or c.get("pdf_page") in pages)
        for c in response.get("citations", [])
    )


def ask(url: str, token: str | None, case: dict[str, Any]) -> tuple[dict[str, Any], float]:
    body = {"question": case["question"], "language": case.get("language", "fr")}
    if case.get("include_classified"):
        body["include_classified"] = True
    headers = {"Content-Type": "application/json"} | ({"X-Internal-Token": token} if token else {})
    request = urllib.request.Request(f"{url}/ask", data=json.dumps(body).encode(), headers=headers)
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=300) as reply:
        return json.loads(reply.read()), time.monotonic() - started


def summarize(outcomes: list[Outcome]) -> dict[str, Any]:
    questions = [o for o in outcomes if not o.trap]
    traps = [o for o in outcomes if o.trap]
    return {
        "questions": len(questions),
        "accuracy": round(sum(o.passed for o in questions) / len(questions), 4) if questions else 0.0,
        "traps": len(traps),
        "traps_refused": sum(o.passed for o in traps),
        "median_s": round(statistics.median(o.seconds for o in outcomes), 2) if outcomes else 0.0,
        "failed": [o.case_id for o in outcomes if not o.passed],
    }


def accepted(summary: dict[str, Any]) -> bool:
    return (
        summary["accuracy"] >= MIN_ACCURACY
        and summary["traps_refused"] == summary["traps"]
        and summary["median_s"] <= MAX_MEDIAN_S
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("testset", type=Path)
    parser.add_argument("--url", default="http://127.0.0.1:8400")
    parser.add_argument("--token", default=None, help="Jeton interne du service, s'il en exige un")
    args = parser.parse_args()
    lines = args.testset.read_text(encoding="utf-8").splitlines()
    outcomes = []
    for case in (json.loads(line) for line in lines if line.strip()):
        response, seconds = ask(args.url.rstrip("/"), args.token, case)
        outcomes.append(Outcome(case["id"], bool(case.get("trap")), judge(case, response), seconds))
    summary = summarize(outcomes)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if accepted(summary) else 1


if __name__ == "__main__":
    sys.exit(main())
