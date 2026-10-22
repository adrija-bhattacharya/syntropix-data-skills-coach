"""Mistake -> the exact video moment that fixes it.

The graders already say *why* an answer is wrong: they compare the learner's
output with the right one and name the mistake (``null_equality``,
``join_fanout``, ``dropped_unmatched``, ...; see :mod:`practice.fingerprint`)
and the topic it points at.  This module turns that diagnosis into the one
stretch of a checked video that explains it:

1. **what the clip must talk about** - a short description of the mistake
   (:data:`MISTAKE_TOPICS`), the blamed topic's name and the grader's own
   message;
2. **where** - every chapter of every library video for that skill
   (``harvest/data/video_segments.json``) is scored by IDF-weighted overlap
   with that description (stemmed, British/American spelling folded), plus a
   small bonus when the semantic video check (``video_checks.json``) already
   verified the video for that topic;
3. **how long** - the clip runs from the chapter's start to the next chapter's
   start, capped at :data:`MAX_CLIP_S`.

When no chapter matches well enough, the fallback is the topic-level jump
point of the best checked lesson for the blamed topic (``kind="topic"``).
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from functools import cache
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parent / "harvest" / "data"
MIN_SCORE = 0.3  # below this a chapter is not "about" the mistake
MAX_CLIP_S = 600
LAST_CHAPTER_S = 300  # length assumed for a video's last chapter

# What a clip has to explain for each mistake the graders can name.  Distractor
# codes that aren't listed fall back to the grader's message + the topic name.
MISTAKE_TOPICS: dict[str, str] = {
    # SQL (practice.fingerprint)
    "null_equality": "is null operator null values",
    "count_star_outer": "count null values",
    "aggregate_in_where": "having clause filter groups",
    "aggregate_misuse": "aggregate functions group by",
    "having_without_group": "group by having",
    "missing_group_by": "group by aggregate",
    "missing_groupby": "group by aggregate",
    "wrong_grouping": "group by",
    "join_fanout": "join one to many duplicates",
    "join_duplicates": "join duplicates",
    "duplicates": "distinct duplicates",
    "dropped_unmatched": "left join outer join",
    "collapsed_window": "window functions over partition",
    "missing_partition": "partition by window functions",
    "window_misuse": "window functions over",
    "misuse_window": "window functions over",
    "unfiltered": "where clause filter",
    "unlimited": "limit top",
    "wrong_order": "order by sort",
    "wrong_direction": "order by descending sort",
    "ascending": "sort descending ascending",
    "wrong_columns": "select clause columns",
    "unknown_name": "select columns table",
    "ambiguous_column": "alias join table",
    "case_boundary": "case when statement",
    # pandas / Python (practice.catalogue._py_rules)
    "nan_equality": "missing values isna nan null",
    "series_and_or": "boolean filtering multiple conditions",
    "merge_fanout": "merge join duplicates",
    "unknown_key": "select columns loc",
    "no_result": "variables",
    # Excel (practice.excel)
    "vlookup_approx": "vlookup exact match",
    "missing_anchor": "absolute references dollar sign",
    "no_equals": "formulas",
    "excel_error": "formula errors",
    "no_trim": "trim extra spaces clean text",
}


@dataclass(frozen=True, slots=True)
class Moment:
    video_id: str
    title: str
    channel: str
    start: int  # seconds
    end: int
    chapter: str
    score: float
    kind: str  # "chapter": a chapter about the mistake | "topic": the topic's jump point
    why: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ------------------------------------------------------------------ tokens
_STOP = set(
    "the a an and or of to in on for with is are be this that it as by at from you your we our i "  # noqa: SIM905
    "how what why when which can will use using into about learn tutorial course video full part "
    "beginners beginner guide step easy minutes min hour hours introduction intro explained "
    "sql python excel pandas don't doesn't not never only one each every".split()
)


def tokens(text: str) -> set[str]:
    from harvest.library import _norm, _stem

    t = re.sub(r"\buse cases?\b", " ", _norm(text.replace("_", " ")))  # "Use case: ..." isn't CASE
    words = re.findall(r"[a-z][a-z0-9_+#]*", t)
    return {_stem(w) for w in words if w not in _STOP and len(w) > 1}


# -------------------------------------------------------------------- data
@cache
def _library() -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
    lib = json.loads((DATA / "library.json").read_text(encoding="utf-8"))
    videos = {v["video_id"]: v for v in lib["videos"]}
    seg_file = DATA / "video_segments.json"
    segs = json.loads(seg_file.read_text(encoding="utf-8"))["videos"] if seg_file.exists() else {}
    chk_file = DATA / "video_checks.json"
    checks = json.loads(chk_file.read_text(encoding="utf-8")) if chk_file.exists() else {}
    return videos, segs, checks


@cache
def _index(
    domains: tuple[str, ...],
) -> tuple[list[tuple[str, int, int, str, set[str]]], dict[str, float]]:
    """Every chapter of the domains' videos: (video, start, end, title, tokens), plus IDF."""
    videos, segs, _ = _library()
    rows: list[tuple[str, int, int, str, set[str]]] = []
    for vid, s in segs.items():
        if vid not in videos or videos[vid]["domain"] not in domains:
            continue
        chapters = s["segments"]
        for i, (start, title) in enumerate(chapters):
            nxt = (
                chapters[i + 1][0]
                if i + 1 < len(chapters)
                else min(s["seconds"], start + LAST_CHAPTER_S)
            )
            end = min(int(nxt), start + MAX_CLIP_S)
            if end - start < 20:
                continue
            rows.append((vid, int(start), end, title, tokens(title)))
    df: dict[str, int] = {}
    for *_, toks in rows:
        for t in toks:
            df[t] = df.get(t, 0) + 1
    n = max(1, len(rows))
    idf = {t: math.log(1 + n / c) for t, c in df.items()}
    return rows, idf


def _bonus(vid: str, concept: str) -> float:
    videos, _, checks = _library()
    v, c = videos.get(vid, {}), checks.get(vid, {})
    b = 0.0
    if v.get("concept") == concept and c.get("level") == "verified":
        b += 0.15
    elif concept in (c.get("coverage") or []):
        b += 0.1
    return b


# -------------------------------------------------------------------- find
def find(
    *,
    domain: str,
    concept: str,
    concept_name: str,
    code: str,
    message: str = "",
    top: int = 2,
    extra_domains: Iterable[str] = (),
) -> list[Moment]:
    """The best clips for one diagnosed mistake, at most one per video."""
    videos, _, checks = _library()
    rows, idf = _index(tuple(sorted({domain, *extra_domains})))
    phrase = tokens(MISTAKE_TOPICS.get(code, ""))
    topic = tokens(concept_name) | tokens(concept)
    weight = dict.fromkeys(topic, 0.5) | dict.fromkeys(phrase, 1.0)  # the mistake counts most
    msg = tokens(message) - set(weight)
    denom = sum(idf.get(t, 0.0) * w for t, w in weight.items()) or 1.0
    scored: list[tuple[float, tuple[str, int, int, str, set[str]]]] = []
    for row in rows:
        toks = row[4]
        if not (toks & topic or len(toks & phrase) >= 2):
            continue  # a chapter must name the topic, or two words of the mistake
        hit = sum(idf[t] * weight[t] for t in toks & set(weight)) + 0.3 * sum(
            idf[t] for t in toks & msg
        )
        score = hit / denom + _bonus(row[0], concept)
        scored.append((score, row))
    scored.sort(key=lambda x: (-x[0], x[1][1]))
    out: list[Moment] = []
    seen: set[str] = set()
    for score, (vid, start, end, title, _t) in scored:
        if score < MIN_SCORE or vid in seen:
            continue
        v = videos[vid]
        seen.add(vid)
        out.append(
            Moment(
                vid, v["title"], v.get("channel", ""), start, end, title,
                round(score, 3), "chapter", f'The chapter "{title}" covers this mistake.',
            )
        )  # fmt: skip
        if len(out) >= top:
            return out
    # fallback: the topic's own checked lesson, at its jump point
    for vid, v in videos.items():
        if len(out) >= top:
            break
        c = checks.get(vid, {})
        if (
            vid in seen
            or v.get("concept") != concept
            or c.get("level") not in ("verified", "related")
        ):
            continue
        start = int(c.get("start") or 0)
        out.append(
            Moment(
                vid, v["title"], v.get("channel", ""), start,
                start + min(MAX_CLIP_S, int(v.get("minutes", 10) * 60) - start),
                c.get("chapter", ""), 0.0, "topic", f"A checked lesson on {concept_name}.",
            )
        )  # fmt: skip
        seen.add(vid)
    return out


def _extra(domain: str, kind: str) -> tuple[str, ...]:
    """Skills whose videos also teach a task's mistakes (a pipeline's SQL is SQL)."""
    if kind == "sql" and domain != "sql":
        return ("sql",)
    if kind == "python" and domain == "python_data":
        return ("python",)
    return ()


def for_answer(
    domain: str, kind: str, diagnoses: Iterable[Any], names: dict[str, str], top: int = 2
) -> dict[str, Any] | None:
    """The clips for a wrong answer's strongest diagnosis (``None`` when there is none)."""
    ds = sorted(diagnoses, key=lambda d: -d.weight)
    if not ds:
        return None
    d = ds[0]
    moments = find(
        domain=domain, concept=d.concept, concept_name=names.get(d.concept, d.concept),
        code=d.code, message=d.message, top=top, extra_domains=_extra(domain, kind),
    )  # fmt: skip
    if not moments:
        return None
    return {
        "code": d.code,
        "concept_id": d.concept,
        "concept": names.get(d.concept, d.concept),
        "moments": [m.as_dict() for m in moments],
    }
