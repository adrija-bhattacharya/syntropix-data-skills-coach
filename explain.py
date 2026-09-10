"""Deterministic, knowledge-graph-grounded reason strings for each plan step.

Template fill only - never free-form generation - so it is reproducible and
auditable.
"""

from __future__ import annotations

from dataclasses import replace

from algorithms.dynamic_programming import Plan
from config import settings
from model.knowledge_graph import KnowledgeGraph
from model.learner import LearnerState


def _name(kg: KnowledgeGraph, cid: str) -> str:
    c = kg.concepts.get(cid)
    return c.name if c else cid


def explain_step(
    kg: KnowledgeGraph,
    resource_id: str,
    concept_id: str,
    state: LearnerState,
    prev_difficulty: float | None = None,
) -> str:
    r = kg.resources[resource_id]
    parts = [f"Builds **{_name(kg, concept_id)}**"]

    prereqs = sorted(kg.prerequisites_of_resource(resource_id))
    if not prereqs:
        parts.append("no prerequisites")
    else:
        already = [p for p in prereqs if state.is_mastered(p)]
        pending = [p for p in prereqs if not state.is_mastered(p)]
        theta = settings.mastery_threshold
        if already and not pending:
            parts.append(
                f"prerequisite{'s' if len(already) != 1 else ''} "
                f"{', '.join(_name(kg, p) for p in already)} already >= {theta:g} mastered"
            )
        elif pending:
            parts.append(
                f"prerequisite{'s' if len(pending) != 1 else ''} "
                f"{', '.join(_name(kg, p) for p in pending)} covered by earlier steps in this plan"
            )

    if prev_difficulty is not None:
        delta = r.difficulty - prev_difficulty
        parts.append(f"difficulty {r.difficulty:g} ({'+' if delta >= 0 else '-'}{abs(delta):g})")
    else:
        parts.append(f"difficulty {r.difficulty:g}")

    if r.kind != "lesson":
        parts.append(f"type: {r.kind}")
    return "; ".join(parts) + "."


def explain_plan(kg: KnowledgeGraph, plan: Plan, state: LearnerState) -> Plan:
    if not plan.feasible or not plan.steps:
        return plan
    reasons: list[str] = []
    prev = 1.0
    for i, (rid, cid) in enumerate(zip(plan.steps, plan.concepts)):
        if plan.is_review(i):
            reasons.append(
                f"Spaced review of **{_name(kg, cid)}** - taught earlier and predicted to have "
                f"decayed below the mastery threshold before it is needed again."
            )
        else:
            reasons.append(explain_step(kg, rid, cid, state, prev_difficulty=prev))
        prev = kg.resources[rid].difficulty
    return replace(plan, reasons=tuple(reasons))
