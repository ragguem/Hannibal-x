from doctrine_eval import Outcome, accepted, judge, summarize

ANSWER = {"status": "answered", "citations": [{"publication": "DEMO-MANUEL", "pdf_page": 12}]}
REFUSAL = {"status": "refused", "citations": []}


def test_answer_must_cite_the_expected_publication_and_page() -> None:
    assert judge({"publication": "DEMO-MANUEL", "pdf_pages": [12]}, ANSWER)
    assert not judge({"publication": "DEMO-MANUEL", "pdf_pages": [40]}, ANSWER)
    assert not judge({"publication": "AUTRE"}, ANSWER)
    assert not judge({"publication": "DEMO-MANUEL"}, REFUSAL)


def test_trap_passes_only_when_refused() -> None:
    assert judge({"trap": True}, REFUSAL)
    assert not judge({"trap": True}, ANSWER)


def test_acceptance_needs_accuracy_every_trap_and_latency() -> None:
    outcomes = [Outcome(f"q{i}", False, i != 0, 6.0) for i in range(20)] + [Outcome("t1", True, True, 2.0)]
    summary = summarize(outcomes)

    assert summary["accuracy"] == 0.95
    assert summary["failed"] == ["q0"]
    assert accepted(summary)
    assert not accepted(summary | {"traps_refused": 0})
    assert not accepted(summary | {"median_s": 9.0})
