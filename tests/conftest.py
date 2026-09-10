from __future__ import annotations

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import pytest

from config import seed_everything
from curriculum import build_curriculum
from model.knowledge_graph import KnowledgeGraph
from model.learner import LearnerState


@pytest.fixture(autouse=True)
def _seed() -> None:
    seed_everything()


@pytest.fixture
def kg() -> KnowledgeGraph:
    return build_curriculum()


@pytest.fixture
def cold(kg: KnowledgeGraph) -> LearnerState:
    return LearnerState.cold_start(kg.concept_ids, time_budget_s=6000)
