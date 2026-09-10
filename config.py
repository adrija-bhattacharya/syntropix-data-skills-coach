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
