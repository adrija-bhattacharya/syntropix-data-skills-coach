from __future__ import annotations

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import pytest

from velpo.config import seed_everything
from velpo.curriculum import build_curriculum
from velpo.model.knowledge_graph import KnowledgeGraph
from velpo.model.learner import LearnerState


@pytest.fixture(autouse=True)
def _seed() -> None:
    seed_everything()


@pytest.fixture
def kg() -> KnowledgeGraph:
    return build_curriculum()


@pytest.fixture
def cold(kg: KnowledgeGraph) -> LearnerState:
    return LearnerState.cold_start(kg.concept_ids, time_budget_s=6000)
