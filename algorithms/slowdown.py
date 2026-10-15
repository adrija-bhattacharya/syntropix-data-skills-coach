"""A slowdown is a symptom (claim G2): unexpected slow learning points at a gap.

Velocity predicts velocity: how fast a learner picked up what a topic builds on
predicts how fast they'll pick up the topic (``predicted_velocity``).  When the
*measured* velocity on a topic falls far below that prediction, something the
topic needs is missing.  Two explanations are checked, in order:

1. **a weak stated prerequisite** - a prerequisite the learner hasn't mastered
   (or has forgotten): refresh it first;
2. **a missing prerequisite** - a concept the graph does *not* list as a
   prerequisite but that the learner is weak on and that sits in the same
   neighbourhood (shares ancestors or descendants with the slow topic).  The top
   suspect becomes evidence on that candidate edge for the self-healing graph
   (claim D), so the graph itself can learn the missing link.

Suspects are ranked by ``(1 - mastery) x proximity``: weak *and* structurally
close, doubled for a concept the plan put before the slow topic (it was meant
to be known by now).  Nothing is flagged for a topic learned at or above ``threshold`` of its
prediction.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from algorithms.velocity_schedule import predicted_velocity

THRESHOLD = 0.55  # measured < 55% of predicted -> flag
WEAK = 0.6  # mastery under this counts as a gap


@dataclass(frozen=True, slots=True)
class Suspect:
    concept: str
    kind: str  # "weak_prerequisite" | "missing_prerequisite"
    score: float
    mastery: float


@dataclass(frozen=True, slots=True)
class Slowdown:
    concept: str
    measured: float
    expected: float
    ratio: float  # measured / expected
    suspects: tuple[Suspect, ...] = field(default_factory=tuple)


def _ancestors(prereqs: Mapping[str, Sequence[str]]) -> dict[str, set[str]]:
    memo: dict[str, set[str]] = {}

    def go(c: str) -> set[str]:
        if c not in memo:
            memo[c] = set()
            for p in prereqs.get(c, ()):
                memo[c] |= {p, *go(p)}
        return memo[c]

    for c in prereqs:
        go(c)
    return memo


def detect(
    concepts: Sequence[str],
    prereqs: Mapping[str, Sequence[str]],
    velocity: Mapping[str, float],
    observed: set[str],
    mastery: Mapping[str, float],
    *,
    threshold: float = THRESHOLD,
    top: int = 3,
    order: Sequence[str] | None = None,
) -> list[Slowdown]:
    """``order``: the plan's order of concepts.  A concept the plan put *before*
    the slow topic but that the learner still hasn't mastered is the likeliest
    missing link (it was meant to be known by now), so it scores double."""
    pos = {c: i for i, c in enumerate(order or concepts)}
    anc = _ancestors({c: list(prereqs.get(c, ())) for c in concepts})
    desc: dict[str, set[str]] = {c: set() for c in concepts}
    for c, ups in anc.items():
        for x in ups:
            desc.setdefault(x, set()).add(c)
    out: list[Slowdown] = []
    for b in concepts:
        if b not in observed or b not in velocity:
            continue
        # the prediction for b without b's own measurement
        expected = predicted_velocity([b], prereqs, velocity, observed - {b})[b]
        ratio = velocity[b] / expected if expected > 0 else 1.0
        if ratio >= threshold:
            continue
        suspects: list[Suspect] = []
        for p in prereqs.get(b, ()):
            m = mastery.get(p, 0.0)
            if m < WEAK:
                suspects.append(Suspect(p, "weak_prerequisite", round(1.0 - m, 3), round(m, 3)))
        for a in concepts:
            if a == b or a in anc.get(b, set()) or a in desc.get(b, set()):
                continue  # already upstream, or downstream (would make a cycle)
            m = mastery.get(a, 0.0)
            if m >= WEAK:
                continue
            shared = len(anc.get(a, set()) & anc.get(b, set())) + len(
                desc.get(a, set()) & desc.get(b, set())
            )
            proximity = (1.0 + shared) * (2.0 if pos.get(a, 1e9) < pos.get(b, 1e9) else 1.0)
            suspects.append(
                Suspect(a, "missing_prerequisite", round((1.0 - m) * proximity, 3), round(m, 3))
            )
        suspects.sort(key=lambda s: (s.kind != "weak_prerequisite", -s.score))
        out.append(
            Slowdown(
                b, round(velocity[b], 3), round(expected, 3), round(ratio, 3), tuple(suspects[:top])
            )
        )
    return sorted(out, key=lambda s: s.ratio)
