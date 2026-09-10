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

Ability is estimated by **expected a posteriori** (EAP) over a grid with a
standard-normal prior - stable for the 4-8 items a CAT actually administers,
where maximum likelihood can diverge.

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
def eap_estimate(
    responses: Sequence[tuple[Item, bool]], *, prior_sd: float = 1.5
) -> tuple[float, float]:
    """Posterior mean and SD of ``theta`` under a ``N(0, prior_sd)`` prior.

    A mildly informative prior keeps the estimate finite when a learner answers
    a short block all-right or all-wrong (where MLE would run off to +/-inf).
    """
    if not responses:
        return 0.0, prior_sd
    log_post = -0.5 * (_GRID / prior_sd) ** 2
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
    max_items_per_skill: int = field(default_factory=lambda: settings.assess_max_items_per_skill)
    se_target: float = field(default_factory=lambda: settings.assess_se_target)
    responses: dict[str, list[Response]] = field(default_factory=dict)
    _asked: set[str] = field(default_factory=set)
    _pending: Item | None = None

    def __post_init__(self) -> None:
        for s in self.skills:
            self.responses.setdefault(s, [])

    # -- estimation ------------------------------------------------------
    def _pairs(self, skill: str) -> list[tuple[Item, bool]]:
        return [(self.bank.items[r.item_id], r.correct) for r in self.responses[skill]]

    def estimate(self, skill: str) -> SkillEstimate:
        theta, se = eap_estimate(self._pairs(skill))
        return SkillEstimate(skill, theta, se, len(self.responses[skill]))

    def estimates(self) -> dict[str, SkillEstimate]:
        return {s: self.estimate(s) for s in self.skills}

    def to_mastery(self) -> dict[str, float]:
        return {s: e.mastery for s, e in self.estimates().items()}

    # -- flow ----------------------------------------------------------
    def _needs_more(self, skill: str) -> bool:
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
