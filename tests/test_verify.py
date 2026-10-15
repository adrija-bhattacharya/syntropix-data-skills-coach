"""Semantic video checks (harvest/verify.py): offline, with fake evidence."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from harvest.verify import (
    ClaudeJudge,
    Evidence,
    LocalJudge,
    parse_chapters,
    topic_profiles,
    verify,
)

DESC = """In this course you'll learn SQL from scratch.

Contents
⌨️ (0:00) Introduction
⌨️ (2:36) SELECT and WHERE
⌨️ (12:10) GROUP BY and HAVING
⌨️ (25:00) Window functions: ROW_NUMBER, RANK and PARTITION BY
⌨️ (1:02:03) Self joins
Follow us: https://example.com"""


def test_chapters_are_read_from_descriptions() -> None:
    ch = parse_chapters(DESC)
    assert ch[0] == (0, "Introduction")
    assert (1500, "Window functions: ROW_NUMBER, RANK and PARTITION BY") in ch
    assert ch[-1] == (3723, "Self joins")
    assert parse_chapters("Great video! Check 12:00 for the answer.") == []  # not a chapter list


def test_topic_profiles_are_rich() -> None:
    p = topic_profiles("sql")
    assert "PARTITION BY" in p["window_functions"] or "OVER" in p["window_functions"]
    assert len(p["window_functions"].split()) > 30


def test_local_judge_is_discriminative_and_finds_the_moment() -> None:
    j = LocalJudge(topic_profiles("sql"))
    ev = Evidence("description", DESC, parse_chapters(DESC))
    good = j.lesson("window_functions", ev)
    assert good.teaches and good.start == 1500 and "Window functions" in good.chapter
    wrong = j.lesson("window_functions", Evidence("title", "MySQL: SUBQUERIES", []))
    assert not wrong.teaches and wrong.level == "off-topic"
    right = j.lesson("subqueries", Evidence("title", "MySQL: SUBQUERIES", []))
    assert right.teaches and right.rank == 1
    course = j.course(ev)
    assert course.level == "covers" and {"window_functions", "self_join"} <= set(course.coverage)


class FakeClaude:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.seen: list[str] = []
        self.messages = self

    def create(self, **kw: Any) -> Any:
        self.seen.append(kw["messages"][0]["content"])
        return SimpleNamespace(content=[SimpleNamespace(text=self.answer)])


def test_claude_judge_parses_json_and_falls_back() -> None:
    profiles = topic_profiles("sql")
    names = {"window_functions": "Window functions"}
    fake = FakeClaude(
        '{"teaches": true, "confidence": 0.9, "start_seconds": 1500, "reason": "Teaches OVER()."}'
    )
    j = ClaudeJudge(profiles, names, client=fake)
    v = j.lesson(
        "window_functions",
        Evidence("transcript", "today we use OVER ...", [(0, "x")]),
        {"title": "T"},
    )
    assert v.teaches and v.level == "verified" and v.start == 1500 and v.judge == "claude"
    assert "Window functions" in fake.seen[0]
    broken = ClaudeJudge(profiles, names, client=FakeClaude("no json here"))
    v2 = broken.lesson("window_functions", Evidence("title", "MySQL: SUBQUERIES", []), {})
    assert v2.judge == "local" and not v2.teaches  # fell back to the local judge


def test_verify_keeps_good_verdicts_and_rechecks_weak_ones() -> None:
    lib = {
        "videos": [
            {"video_id": "a" * 11, "title": "SQL Window Functions explained", "channel": "c",
             "domain": "sql", "concept": "window_functions", "kind": "lesson"},
            {"video_id": "b" * 11, "title": "Full SQL course", "channel": "c",
             "domain": "sql", "concept": None, "kind": "course"},
        ]
    }  # fmt: skip
    calls: list[str] = []

    def fetch(v: dict[str, Any]) -> Evidence:
        calls.append(v["video_id"])
        return Evidence("description", f"{v['title']}. {DESC}", parse_chapters(DESC))

    out = verify(lib, fetch, judge_factory=lambda p, n: LocalJudge(p))
    assert out["a" * 11]["level"] == "verified" and out["b" * 11]["level"] == "covers"
    again = verify(lib, fetch, out, judge_factory=lambda p, n: LocalJudge(p))
    assert again == out and len(calls) == 2  # cached: nothing fetched twice
    weak = {**out, "a" * 11: {**out["a" * 11], "source": "title"}}
    verify(lib, fetch, weak, judge_factory=lambda p, n: LocalJudge(p))
    assert calls[-1] == "a" * 11  # title-only verdicts are re-checked


def test_boilerplate_is_dropped_and_the_title_counts_most() -> None:
    from harvest.verify import clean_description, evidence_text

    desc = "Subscribe for more!\nhttps://patreon.com/x\nLearn GROUP BY in pandas\n#python #data"
    assert clean_description(desc) == "Learn GROUP BY in pandas"
    j = LocalJudge(topic_profiles("python_data"))
    title = "Group By and Aggregate Functions in Pandas"
    noisy = "Follow me on instagram\nDiscord: https://x\n" + "Grab the merch, use coupon CODE\n" * 5
    ev = Evidence("description", evidence_text(title, clean_description(noisy)), [])
    assert j.lesson("groupby_agg", ev).teaches
