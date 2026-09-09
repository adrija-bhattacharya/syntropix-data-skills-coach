"""Orchestration: knowledge graph + learner store + solver + explanations.

The single entry point the FastAPI service calls.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Literal, Protocol

from velpo.algorithms.astar import solve_astar
from velpo.algorithms.dynamic_programming import (
    Plan,
    TeacherConstraints,
    solve_optimal,
    solve_pareto,
)
from velpo.config import settings
from velpo.explain import explain_plan, explain_step
from velpo.model.cost import build_cost_vectors
from velpo.model.knowledge_graph import KnowledgeGraph
from velpo.model.learner import Attempt, LearnerState, bkt_update, decay, velocity_update

Mode = Literal["optimal", "interactive", "pareto"]
_HOUR = 3600.0


class LearnerStore(Protocol):
    def get(self, learner_id: str) -> LearnerState | None: ...
    def put(self, learner_id: str, state: LearnerState) -> None: ...


class MemoryStore:
    def __init__(self) -> None:
        self._d: dict[str, LearnerState] = {}

    def get(self, learner_id: str) -> LearnerState | None:
        return self._d.get(learner_id)

    def put(self, learner_id: str, state: LearnerState) -> None:
        self._d[learner_id] = state


class Engine:
    def __init__(self, kg: KnowledgeGraph, store: LearnerStore | None = None) -> None:
        self.kg = kg
        self.store = store or MemoryStore()

    # ------------------------------------------------------------- learner
    def ensure(self, learner_id: str, *, time_budget_s: float) -> LearnerState:
        state = self.store.get(learner_id)
        if state is None:
            difficulty = {
                c: max(
                    (self.kg.resources[r].difficulty for r in self.kg.resources_for(c)), default=1.0
                )
                for c in self.kg.concept_ids
            }
            state = LearnerState.cold_start(
                self.kg.concept_ids, time_budget_s=time_budget_s, difficulty=difficulty
            )
            self.store.put(learner_id, state)
        return state

    # ------------------------------------------------------------- recommend
    def recommend(
        self,
        learner_id: str,
        goals: Sequence[str],
        *,
        time_budget_s: float,
        mode: Mode = "optimal",
        n_paths: int = 1,
        constraints: TeacherConstraints | None = None,
    ) -> list[Plan]:
        state = replace(
            self.ensure(learner_id, time_budget_s=time_budget_s), time_budget_s=time_budget_s
        )
        costs = build_cost_vectors(self.kg, state)
        goal_list = list(goals)

        if mode == "pareto" or n_paths > 1:
            plans = solve_pareto(self.kg, goal_list, state, costs, constraints=constraints)
            plans = plans[:n_paths] if n_paths > 0 else plans
        elif mode == "interactive":
            result = solve_astar(self.kg, goal_list, state, costs, constraints=constraints)
            plans = [result if isinstance(result, Plan) else result[0]]
        else:
            plans = [solve_optimal(self.kg, goal_list, state, costs, constraints=constraints)]

        explained = [explain_plan(self.kg, p, state) for p in plans if p.feasible]
        return explained or plans

    # ------------------------------------------------------------- observe
    def observe(self, learner_id: str, attempt: Attempt) -> LearnerState:
        state = self.store.get(learner_id)
        if state is None:
            raise KeyError(f"unknown learner {learner_id!r}")
        r = self.kg.resources.get(attempt.resource_id)
        if r is None:
            raise KeyError(f"unknown resource {attempt.resource_id!r}")

        state = state.copy()
        now = attempt.at or (state.now_s + attempt.seconds)
        for c in r.concepts:
            prior = decay(
                state.mastery.get(c, settings.bkt_p_init),
                max(0.0, (now - state.last_seen.get(c, 0.0)) / _HOUR),
                state.half_life.get(c, settings.forgetting_half_life_h),
            )
            post = bkt_update(prior, attempt.correct)
            state.velocity[c] = velocity_update(
                state.velocity.get(c, 1.0), post - prior, attempt.seconds / max(1, len(r.concepts))
            )
            state.mastery[c] = post
            state.last_seen[c] = now
        state.recent.append(attempt)
        state.recent[:] = state.recent[-32:]
        state.now_s = now
        state.n_interactions += 1
        state.time_budget_s = max(0.0, state.time_budget_s - attempt.seconds)
        self.store.put(learner_id, state)
        return state

    # ------------------------------------------------------------- explain
    def explain(self, learner_id: str, resource_id: str) -> str:
        state = self.store.get(learner_id) or self.ensure(learner_id, time_budget_s=3600.0)
        return explain_step(self.kg, resource_id, self.kg.resources[resource_id].concepts[0], state)
