"""Orchestration: knowledge graph + learner store + solver + explanations.

The single entry point the FastAPI service calls.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from algorithms.roleplan import RolePlan

from algorithms.astar import solve_astar
from algorithms.dynamic_programming import (
    Plan,
    TeacherConstraints,
    solve_optimal,
    solve_pareto,
)
from algorithms.graph_traversal import ancestors_subgraph
from algorithms.sequencing import SequencePlan, plan_sequence
from config import settings
from explain import explain_plan, explain_step
from model.assessment import AdaptiveSession, ItemBank
from model.cost import build_cost_vectors
from model.knowledge_graph import KnowledgeGraph
from model.learner import Attempt, LearnerState, bkt_update, decay, velocity_update

Mode = Literal["sequence", "optimal", "interactive", "pareto"]
_HOUR = 3600.0


def _sequence_to_plan(kg: KnowledgeGraph, sp: SequencePlan) -> Plan:
    return Plan(
        steps=tuple(s.resource_id for s in sp.steps),
        concepts=tuple(s.concept for s in sp.steps),
        objective=sp.objective,
        total_seconds=sp.total_seconds,
        feasible=sp.feasible,
        note=sp.note,
        reviews=tuple(s.review for s in sp.steps),
        checks=tuple(s.check for s in sp.steps),
        sessions=sp.sessions,
    )


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
    def __init__(
        self,
        kg: KnowledgeGraph,
        store: LearnerStore | None = None,
        *,
        item_bank: ItemBank | None = None,
    ) -> None:
        self.kg = kg
        self.store = store or MemoryStore()
        self.item_bank = item_bank
        self._assessments: dict[str, AdaptiveSession] = {}

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

    # ------------------------------------------------------- assessment (capability)
    def start_assessment(
        self,
        learner_id: str,
        goals: Sequence[str],
        *,
        time_budget_s: float = 3600.0,
        band: str = "intermediate",
    ) -> AdaptiveSession:
        """Begin an adaptive diagnostic over the goals' prerequisite closure.

        ``band`` is the learner's self-reported starting level; it sets the prior
        the adaptive test starts from.  A beginner mostly keeps what they said.
        """
        if self.item_bank is None:
            raise RuntimeError("this engine has no item bank")
        relevant = set(ancestors_subgraph(self.kg.prereq, list(goals)).nodes) or set(goals)
        skills = [s for s in self.item_bank.skills if s in relevant]
        session = AdaptiveSession(self.item_bank, skills=skills or self.item_bank.skills, band=band)
        self._assessments[learner_id] = session
        self.ensure(learner_id, time_budget_s=time_budget_s)  # placeholder state
        return session

    def assessment(self, learner_id: str) -> AdaptiveSession:
        try:
            return self._assessments[learner_id]
        except KeyError:
            raise KeyError(f"no active assessment for {learner_id!r}") from None

    def answer_assessment(
        self, learner_id: str, item_id: str, response: str | int
    ) -> AdaptiveSession:
        session = self.assessment(learner_id)
        item = session.bank.items.get(item_id)
        if item is None:
            raise KeyError(f"unknown item {item_id!r}")
        session.submit(item_id, item.grade(response))
        if session.done:
            self._apply_assessment(learner_id, session)
        return session

    # ------------------------------------------------------- role-gap plan (claim A)
    def role_plan(
        self,
        learner_id: str,
        role_name: str,
        profile: dict[str, float],
        *,
        time_budget_s: float,
    ) -> RolePlan:
        """Max-hiring-readiness prerequisite-closed set within the budget, sequenced."""
        from algorithms.roleplan import solve_role_plan

        state = replace(
            self.ensure(learner_id, time_budget_s=time_budget_s), time_budget_s=time_budget_s
        )
        prof = {k: v for k, v in profile.items() if k in self.kg.concepts}
        return solve_role_plan(self.kg, role_name, prof, state, budget_minutes=time_budget_s / 60.0)

    def _apply_assessment(self, learner_id: str, session: AdaptiveSession) -> None:
        """Replace the cold-start priors with the CAT-estimated mastery, and keep
        the estimator's per-skill uncertainty for risk-aware planning (claim B)."""
        current = self.store.get(learner_id)
        budget = current.time_budget_s if current else 3600.0
        state = LearnerState.cold_start(self.kg.concept_ids, time_budget_s=budget)
        for c, est in session.estimates().items():
            if c in state.mastery:
                state.mastery[c] = est.mastery
                state.mastery_se[c] = est.se
        self.store.put(learner_id, state)

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
        speed: float = 1.0,
        deadline_s: float | None = None,
    ) -> list[Plan]:
        """``speed`` scales the learner's per-concept velocity (N2) before the
        cost vectors are built: ``> 1`` asks "what does the plan look like for a
        faster learner", ``< 1`` for a slower one.  ``1.0`` uses the estimated
        velocity unchanged.  This is the only knob that makes the *same*
        catalogue + goal produce a different optimal plan per learner.
        """
        state = replace(
            self.ensure(learner_id, time_budget_s=time_budget_s), time_budget_s=time_budget_s
        )
        if speed != 1.0:
            lo, hi = settings.velocity_min, settings.velocity_max
            state = replace(
                state,
                velocity={c: min(hi, max(lo, v * speed)) for c, v in state.velocity.items()},
            )
        costs = build_cost_vectors(self.kg, state)
        goal_list = list(goals)

        if mode == "pareto" or n_paths > 1:
            plans = solve_pareto(self.kg, goal_list, state, costs, constraints=constraints)
            plans = plans[:n_paths] if n_paths > 0 else plans
        elif mode == "interactive":
            result = solve_astar(
                self.kg, goal_list, state, costs, constraints=constraints, deadline_s=deadline_s
            )
            plans = [result if isinstance(result, Plan) else result[0]]
        elif mode == "sequence":
            sp = plan_sequence(
                self.kg,
                goal_list,
                state,
                budget_seconds=time_budget_s,
                constraints=constraints,
            )
            if sp.feasible:
                plans = [_sequence_to_plan(self.kg, sp)]
            else:  # poset too wide (or truly infeasible) -> knapsack + heuristic order
                p = solve_optimal(self.kg, goal_list, state, costs, constraints=constraints)
                note = "sequencing DP not applicable - knapsack fallback" if p.feasible else sp.note
                plans = [replace(p, note=(p.note + "; " + note).strip("; ")) if p.feasible else p]
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
            state.refiner.observe(c, attempt.correct)  # N4: DKT-lite refinement
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
