"""Tunable constants - one place, so runs are reproducible."""

from __future__ import annotations

import random
from dataclasses import dataclass

__version__ = "1.0.0"
SEED = 20260909


@dataclass(frozen=True)
class Settings:
    # --- optimiser -------------------------------------------------------
    mastery_threshold: float = 0.75
    """A prerequisite counts as satisfied once its estimated mastery >= this."""

    budget_buckets: int = 40
    """The time budget is discretised into this many buckets for the DP state
    ``(concept_index, buckets_used)``.  Cost is ``O(V * R * B)``."""

    pareto_epsilon: float = 0.02
    """Grid size for epsilon-pruning the Pareto front (0 = exact)."""

    # --- sequencing DP (algorithms.sequencing) ------------------------
    seq_max_ideals: int = 16_000
    """If the relevant poset has more order ideals than this, the sequencing DP
    is intractable and the engine falls back to knapsack-select + heuristic order."""

    seq_ideal_bound_soft: int = 3_000_000
    """When the cheap ``prod(chain+1)`` bound is between ``seq_max_ideals`` and
    this, count the ideals exactly (capped) before deciding to run or fall back."""

    seq_half_life_steps: float = 9.0
    """Steps after which a concept's post-teaching mastery halves - the decay the
    sequencing DP plans against (why order and review placement matter)."""

    seq_post_mastery: float = 0.9
    """Assumed mastery of a concept immediately after it is taught / reviewed."""

    review_threshold: float = 0.6
    """A covered concept whose predicted mastery drops below this is a review
    candidate for the in-sequence review pass."""

    max_reviews: int = 4
    """Cap on review steps the sequence may insert."""

    session_minutes: float = 35.0
    session_max_load: float = 3.2
    """Per study-session caps the session-packing DP respects."""

    # --- risk-aware planning (claim B) ------------------------------
    risk_kappa: float = 0.7
    """Standard deviations to subtract from a measured skill's logit-mastery
    before the planner acts on it (0 disables risk-aware planning)."""

    risk_confidence_target: float = 0.8
    """Below this ``P(ready)`` for a skill that gates >= 2 downstream concepts,
    the sequencer splices a quick confidence check right after it is taught."""

    risk_max_checks: int = 3
    """Cap on risk-driven confidence-check steps a single plan may insert."""

    # --- role-gap sequencing (algorithms.roleplan) -------------------
    role_max_ideals: int = 60_000
    """Above this many order ideals in the role's relevant poset, the
    max-readiness prerequisite-closed set is chosen greedily instead of exactly."""

    # --- adaptive assessment (model.assessment) ----------------------
    assess_max_items_per_skill: int = 6
    """Hard cap on adaptive items administered per target skill."""

    assess_se_target: float = 0.55
    """Stop testing a skill once the posterior SE of theta drops to this."""

    # --- learner model -------------------------------------------------
    velocity_alpha: float = 0.3
    velocity_min: float = 1e-3
    velocity_max: float = 5.0

    bkt_p_init: float = 0.15
    bkt_p_transit: float = 0.20
    bkt_p_slip: float = 0.10
    bkt_p_guess: float = 0.20

    forgetting_half_life_h: float = 120.0

    # --- scalarised objective weights ---------------------------------
    # order: (-mastery_gain, time, load, difficulty_jump, -review_gain)
    weights: tuple[float, float, float, float, float] = (5.0, 6e-4, 0.4, 0.25, 0.7)


settings = Settings()


def seed_everything(seed: int = SEED) -> None:
    import numpy as np

    random.seed(seed)
    np.random.seed(seed)
