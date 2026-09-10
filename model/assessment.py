"""Adaptive capability assessment - infer the learner's level, don't ask for it.

The learner never rates themselves.  A short **computerised adaptive test**
(CAT) estimates a latent ability ``theta`` per skill from a handful of
difficulty-calibrated items, and each next item is the one that will tell us the
most at the current estimate.

Model
-----
Two-parameter logistic item response theory (2PL):

    P(correct | theta) = sigma(a * (theta - b))          a = discrimination, b = difficulty

Fisher information of an item at ``theta``:

    I(theta) = a^2 * P * (1 - P)

Ability is estimated by **expected a posteriori** (EAP) over a grid.  The prior
mean is set from the learner's self-reported band (beginner / intermediate /
advanced): a beginner keeps a tight low prior and answers only a couple of
confirmation questions, while intermediate / advanced learners get a full
adaptive test that confirms or revises the level from what they answer.  The
prior also keeps the estimate finite where maximum likelihood would diverge.

Item selection is the greedy **maximum-information** rule: administer
``argmax_i I_i(theta_hat)``.  Stop a skill when the posterior SE drops below a
target or a per-skill item cap is hit.

Everything here is pure NumPy - ``O(items * grid)`` per estimate.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import numpy.typing as npt

from config import settings

Floats = npt.NDArray[np.float64]
_GRID: Floats = np.linspace(-4.0, 4.0, 81)


def _sigmoid(x: Floats | float) -> Floats:
    out: Floats = 1.0 / (1.0 + np.exp(-np.asarray(x, dtype=float)))
    return out


def p_correct(theta: Floats | float, a: float, b: float) -> Floats:
    """2PL probability of a correct response."""
    return _sigmoid(a * (np.asarray(theta, dtype=float) - b))


def item_information(theta: float, a: float, b: float) -> float:
    """Fisher information the item carries at ``theta``."""
    p = float(p_correct(theta, a, b))
    return a * a * p * (1.0 - p)


# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Item:
    id: str
    skill: str
    a: float  # discrimination  (~0.6 - 2.5)
    b: float  # difficulty on the logit scale (~-3 - +3)
    stem: str
    kind: str = "mcq"  # "mcq" | "task"
    choices: tuple[str, ...] = ()
    answer_index: int = -1  # mcq: index into choices
    answer_text: str = ""  # task: canonical free-response answer
    tolerance: float = 0.0  # task: numeric tolerance (0 -> exact/string match)

    def grade(self, response: str | int) -> bool:
        if self.kind == "mcq":
            try:
                return int(response) == self.answer_index
            except (ValueError, TypeError):
                return False
        return _match(str(response), self.answer_text, self.tolerance)


def _match(got: str, want: str, tol: float) -> bool:
    got_n, want_n = _num(got), _num(want)
    if got_n is not None and want_n is not None:
        return abs(got_n - want_n) <= max(tol, 1e-9)
    return _norm(got) == _norm(want)


def _num(s: str) -> float | None:
    try:
        return float(s.strip().replace(" ", "").rstrip("."))
    except ValueError:
        return None


def _norm(s: str) -> str:
    return "".join(s.split()).lower()


# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class SkillEstimate:
    skill: str
    theta: float
    se: float
    n_items: int

    @property
    def mastery(self) -> float:
        """Map ability to the [0, 1] mastery the planner's cold-start expects.
        ``theta = 0`` -> 0.5, ``+2`` -> ~0.88, ``-2`` -> ~0.12."""
        return float(_sigmoid(self.theta))

    @property
    def confident(self) -> bool:
        return self.se <= settings.assess_se_target


@dataclass(frozen=True, slots=True)
class Response:
    item_id: str
    correct: bool


# --------------------------------------------------------------------------- #
class ItemBank:
    def __init__(self, items: Iterable[Item]) -> None:
        self.items: dict[str, Item] = {}
        self.by_skill: dict[str, list[str]] = {}
        for it in items:
            self.items[it.id] = it
            self.by_skill.setdefault(it.skill, []).append(it.id)

    def for_skill(self, skill: str) -> list[Item]:
        return [self.items[i] for i in self.by_skill.get(skill, ())]

    @property
    def skills(self) -> list[str]:
        return sorted(self.by_skill)

    @classmethod
    def from_json(cls, path: str | Path) -> ItemBank:
        raw = json.loads(Path(path).read_text())
        return cls(Item(**d) for d in raw)


# --------------------------------------------------------------------------- #
# self-reported starting band -> (prior mean, prior sd, items per skill)
# beginner: the plan "majorly depends on what they say" - a tight low prior and
#           at most one confirmation item per skill.
# intermediate / advanced: the prior is a *starting point* the adaptive test
#           confirms or revises from what they actually answer.
BANDS: dict[str, tuple[float, float, int]] = {
    "beginner": (-1.7, 0.8, 1),
    "intermediate": (0.0, 1.4, 6),
    "advanced": (1.4, 1.2, 5),
}


def eap_estimate(
    responses: Sequence[tuple[Item, bool]], *, prior_mean: float = 0.0, prior_sd: float = 1.5
) -> tuple[float, float]:
    """Posterior mean and SD of ``theta`` under a ``N(prior_mean, prior_sd)`` prior.

    The prior mean is set from the learner's self-reported band; a mildly
    informative prior also keeps the estimate finite when a learner answers a
    short block all-right or all-wrong (where MLE would run off to +/-inf).
    """
    if not responses:
        return prior_mean, prior_sd
    log_post = -0.5 * ((_GRID - prior_mean) / prior_sd) ** 2
    for item, correct in responses:
        p = np.clip(p_correct(_GRID, item.a, item.b), 1e-9, 1 - 1e-9)
        log_post = log_post + np.log(p if correct else 1.0 - p)
    w = np.exp(log_post - log_post.max())
    w /= w.sum()
    theta = float((w * _GRID).sum())
    var = float((w * (_GRID - theta) ** 2).sum())
    return theta, math.sqrt(max(var, 1e-6))


def select_next_item(bank: ItemBank, skill: str, theta: float, asked: set[str]) -> Item | None:
    """Greedy maximum-information item selection."""
    pool = [it for it in bank.for_skill(skill) if it.id not in asked]
    if not pool:
        return None
    return max(pool, key=lambda it: (item_information(theta, it.a, it.b), -it.b, it.id))


# --------------------------------------------------------------------------- #
@dataclass
class AdaptiveSession:
    """One adaptive diagnostic over a set of target skills.

    ``next_question()`` returns the item to administer (``None`` when the whole
    diagnostic is finished); ``submit(item_id, correct)`` records the response.
    """

    bank: ItemBank
    skills: list[str]
    band: str = "intermediate"  # self-reported: beginner | intermediate | advanced
    se_target: float = field(default_factory=lambda: settings.assess_se_target)
    responses: dict[str, list[Response]] = field(default_factory=dict)
    max_items_per_skill: int = 0
    _prior_mean: float = 0.0
    _prior_sd: float = 1.5
    _asked: set[str] = field(default_factory=set)
    _pending: Item | None = None

    def __post_init__(self) -> None:
        for s in self.skills:
            self.responses.setdefault(s, [])
        mean, sd, cap = BANDS.get(self.band, BANDS["intermediate"])
        self._prior_mean, self._prior_sd = mean, sd
        self.max_items_per_skill = cap

    # -- estimation ------------------------------------------------------
    def _pairs(self, skill: str) -> list[tuple[Item, bool]]:
        return [(self.bank.items[r.item_id], r.correct) for r in self.responses[skill]]

    def estimate(self, skill: str) -> SkillEstimate:
        theta, se = eap_estimate(
            self._pairs(skill), prior_mean=self._prior_mean, prior_sd=self._prior_sd
        )
        return SkillEstimate(skill, theta, se, len(self.responses[skill]))

    def estimates(self) -> dict[str, SkillEstimate]:
        return {s: self.estimate(s) for s in self.skills}

    def to_mastery(self) -> dict[str, float]:
        return {s: e.mastery for s, e in self.estimates().items()}

    def style_signal(self) -> dict[str, float | str]:
        """A light 'learning style' read from *how* they answered: hands-on
        (free-response task items) vs recall (multiple choice)."""
        task = [
            r.correct
            for rs in self.responses.values()
            for r in rs
            if self.bank.items[r.item_id].kind == "task"
        ]
        mcq = [
            r.correct
            for rs in self.responses.values()
            for r in rs
            if self.bank.items[r.item_id].kind == "mcq"
        ]
        hands_on = sum(task) / len(task) if task else 0.0
        recall = sum(mcq) / len(mcq) if mcq else 0.0
        note = "balanced"
        if task and mcq and abs(hands_on - recall) >= 0.34:
            note = "stronger on hands-on tasks" if hands_on > recall else "stronger on recall"
        return {"hands_on": round(hands_on, 2), "recall": round(recall, 2), "note": note}

    # -- flow ----------------------------------------------------------
    def _needs_more(self, skill: str) -> bool:
        # a self-declared beginner answers only a few confirmation questions -
        # the plan mostly trusts what they told us.
        if self.band == "beginner" and self.n_answered >= min(len(self.skills), 4):
            return False
        est = self.estimate(skill)
        if est.n_items >= self.max_items_per_skill:
            return False
        if est.confident and est.n_items >= 2:
            return False
        return select_next_item(self.bank, skill, est.theta, self._asked) is not None

    def next_question(self) -> Item | None:
        if self._pending is not None:
            return self._pending
        # administer across skills evenly: the needy skill with the fewest answers
        needy = sorted(
            (s for s in self.skills if self._needs_more(s)),
            key=lambda s: (len(self.responses[s]), s),
        )
        for skill in needy:
            est = self.estimate(skill)
            item = select_next_item(self.bank, skill, est.theta, self._asked)
            if item is not None:
                self._pending = item
                return item
        return None

    def submit(self, item_id: str, correct: bool) -> None:
        item = self.bank.items[item_id]
        if item_id in self._asked:
            raise ValueError(f"item {item_id!r} already answered")
        self.responses[item.skill].append(Response(item_id, correct))
        self._asked.add(item_id)
        self._pending = None

    @property
    def done(self) -> bool:
        return self.next_question() is None

    @property
    def n_answered(self) -> int:
        return len(self._asked)

    def progress(self) -> float:
        """Rough completion fraction for a progress bar."""
        target = sum(
            min(self.max_items_per_skill, max(2, self.max_items_per_skill)) for _ in self.skills
        )
        return min(1.0, self.n_answered / max(1, target)) if not self.done else 1.0
