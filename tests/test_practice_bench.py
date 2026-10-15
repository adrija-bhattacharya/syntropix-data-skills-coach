"""Claim E evidence - execution-verified diagnosis beats outcome-only grading on
learners with a hidden misconception, and costs nothing when there is none."""

from __future__ import annotations

from benchmarks.practice_bench import run


def test_diagnosis_finds_the_hidden_gap_and_gets_learners_there() -> None:
    rows = run(learners=40, write=False)["rows"]
    assert isinstance(rows, list)
    by = {(r["scenario"], r["condition"]): r for r in rows}
    for scenario in {r["scenario"] for r in rows}:
        base, ours = by[(scenario, "outcome-only")], by[(scenario, "execution-verified")]
        if scenario.startswith("control"):
            assert ours["mean_attempts"] == base["mean_attempts"]
            continue
        assert ours["success_rate"] > base["success_rate"]
        assert ours["mean_attempts"] < base["mean_attempts"]
        assert ours["identified_rate"] >= 0.9 and base["identified_rate"] == 0
