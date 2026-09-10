"""Automatic level estimation - map a discovered resource to the 1-5 difficulty
scale the planner already speaks, with no human labelling.

Signals
-------
* **Readability** of the summary - a Flesch-Kincaid grade level (pure Python
  syllable heuristic).  Grade 5 -> difficulty ~1, grade 14+ -> ~5.
* **Jargon density** - fraction of long (>=3 syllable) words in the summary.
* **Title cues** - "introduction / basics / 101" pull down; "advanced / deep
  dive / internals / graduate" pull up.
* **Source & kind priors** - an arXiv paper starts harder than a Wikipedia
  intro; a video is usually a touch gentler than reference docs.

A separate ``quality`` score in [0, 1] (source authority, video like-ratio,
summary completeness) is used only for *ranking* candidates, never for
difficulty.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from harvest.model import RawResource

_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")
_SENT = re.compile(r"[.!?]+")

_EASY_CUES = (
    "introduction",
    "intro to",
    "beginner",
    "basics",
    "getting started",
    "primer",
    "for beginners",
    "101",
    "explained simply",
    "crash course",
    "fundamentals",
)
_HARD_CUES = (
    "advanced",
    "deep dive",
    "in depth",
    "internals",
    "masterclass",
    "graduate",
    "rigorous",
    "formal",
    "theoretical",
    "proof of",
    "from first principles",
)

_SOURCE_PRIOR = {
    "wikipedia": -0.3,
    "wikibooks": -0.1,
    "mdn": 0.4,
    "mit_learn": 0.6,
    "youtube": -0.2,
    "arxiv": 1.8,
}
_KIND_PRIOR = {
    "article": 0.0,
    "book": 0.2,
    "docs": 0.4,
    "course": 0.5,
    "video": -0.2,
    "paper": 1.4,
}


def _syllables(word: str) -> int:
    w = word.lower()
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups)
    if w.endswith("e") and not w.endswith(("le", "ee")) and n > 1:
        n -= 1
    return max(1, n)


def flesch_kincaid_grade(text: str) -> float:
    words = _WORD.findall(text)
    if len(words) < 8:
        return 9.0  # not enough text to judge - assume middle-of-the-road
    sentences = max(1, len([s for s in _SENT.split(text) if s.strip()]))
    syl = sum(_syllables(w) for w in words)
    return 0.39 * (len(words) / sentences) + 11.8 * (syl / len(words)) - 15.59


def jargon_density(text: str) -> float:
    words = _WORD.findall(text)
    if not words:
        return 0.0
    return sum(1 for w in words if _syllables(w) >= 3) / len(words)


@dataclass(frozen=True, slots=True)
class LevelEstimate:
    difficulty: float  # 1.0 - 5.0
    quality: float  # 0.0 - 1.0  (ranking only)
    fk_grade: float
    signals: dict[str, float]


def estimate_level(res: RawResource) -> LevelEstimate:
    fk = flesch_kincaid_grade(res.summary)
    read_d = _clamp(1.0 + (fk - 5.0) / 3.0, 1.0, 5.0)

    jd = jargon_density(res.summary)
    jargon_adj = _clamp(6.0 * (jd - 0.16), -0.6, 1.6)

    title = res.title.lower()
    cue_adj = 0.0
    if any(c in title for c in _EASY_CUES):
        cue_adj -= 1.2
    if any(c in title for c in _HARD_CUES):
        cue_adj += 1.2

    prior = _SOURCE_PRIOR.get(res.source, 0.0) + _KIND_PRIOR.get(res.kind, 0.0)

    difficulty = _clamp(0.62 * read_d + jargon_adj + cue_adj + prior, 1.0, 5.0)

    return LevelEstimate(
        difficulty=round(difficulty, 1),
        quality=_quality(res),
        fk_grade=round(fk, 1),
        signals={
            "readability_difficulty": round(read_d, 2),
            "jargon_adj": round(jargon_adj, 2),
            "title_cue_adj": cue_adj,
            "source_kind_prior": round(prior, 2),
        },
    )


def _quality(res: RawResource) -> float:
    q = {"wikipedia": 0.7, "wikibooks": 0.6, "mdn": 0.85, "mit_learn": 0.8, "arxiv": 0.6}.get(
        res.source, 0.5
    )
    md = res.metadata
    if res.source == "youtube":
        views = float(md.get("views", 0) or 0)
        likes = float(md.get("likes", 0) or 0)
        ratio = likes / views if views > 100 else 0.0
        q = _clamp(0.35 + 40.0 * ratio + (0.15 if views > 50_000 else 0.0), 0.1, 0.95)
    if len(res.summary) < 40:
        q -= 0.15
    return round(_clamp(q, 0.05, 0.98), 3)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))
