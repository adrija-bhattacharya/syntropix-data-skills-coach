"""Orchestration: knowledge graph + learner store + solver + explanations.

The single entry point the FastAPI service calls.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date
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
from algorithms.graph_health import GraphEvidence, GraphHealthReport
from algorithms.graph_traversal import ancestors_subgraph
from algorithms.scheduling import Availability, CalendarPlan, schedule_on_calendar
from algorithms.sequencing import SequencePlan, plan_sequence
from config import settings
from explain import explain_plan, explain_step
from model.assessment import AdaptiveSession, ItemBank
from model.cost import build_cost_vectors
from model.knowledge_graph import KnowledgeGraph
from model.learner import Attempt, LearnerState, bkt_update, decay, scale_velocity, velocity_update
from practice import Diagnosis, ExecResult, Task
from practice.catalogue import ALL_TASKS, BY_ID, CONCEPT_DOMAIN, Graded, grade_task, tasks_for

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


_MAX_ASSESS_SKILLS = 12
"""A skill check probes at most this many skills (~15-25 questions)."""

_PRACTICE_BUDGET_S = 10 * 3600.0
"""Practice re-plans cover the whole path to the goal, not one sitting."""

_REPAIR_MIN_WEIGHT = 0.8
"""Only a *specific* signature (weight >= this) routes a repair task; a weak,
generic one (wrong column count, a syntax error) still lowers the estimate."""


def _weighted_bkt(prior: float, correct: bool, weight: float) -> float:
    """Move ``weight`` of the way from ``prior`` to the BKT posterior."""
    return prior + weight * (bkt_update(prior, correct) - prior)


@dataclass(frozen=True, slots=True)
class PracticeOutcome:
    """What one practice submission did to the learner, the graph and the plan."""

    task_id: str
    correct: bool
    result: ExecResult
    diagnoses: tuple[Diagnosis, ...]
    mastery: dict[str, tuple[float, float]]  # concept -> (before, after)
    edge_evidence: tuple[tuple[str, str, float], ...]  # (a, b, posterior mean of a -> b)
    plan: Plan
    next_task: str | None
    replan_ms: float
    graded: Graded | None = None  # checks, per-row status - for the UI


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
        graph_source: str = "seed",
    ) -> None:
        self.kg = kg
        self.store = store or MemoryStore()
        self.item_bank = item_bank
        self._assessments: dict[str, AdaptiveSession] = {}
        self._solved: dict[str, set[str]] = {}  # learner -> practice tasks passed
        self._repairs: dict[str, set[str]] = {}  # learner -> concepts routed in as repairs
        self.evidence = GraphEvidence.for_graph(kg, source=graph_source)

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
        skills = [s for s in self.item_bank.skills if s in relevant] or self.item_bank.skills
        session = AdaptiveSession(self.item_bank, skills=self._sample_skills(skills), band=band)
        self._assessments[learner_id] = session
        self.ensure(learner_id, time_budget_s=time_budget_s)  # placeholder state
        return session

    def _sample_skills(self, skills: list[str], cap: int = _MAX_ASSESS_SKILLS) -> list[str]:
        """A role graph spans dozens of skills; probing all of them would make the
        check far too long.  Keep ``cap`` skills spread evenly over prerequisite
        depth, so the check samples the basics, the middle and the advanced end."""
        if len(skills) <= cap:
            return skills
        by_depth = sorted(skills, key=lambda s: (len(self.kg.all_prerequisites(s)), s))
        step = (len(by_depth) - 1) / (cap - 1)
        return sorted({by_depth[round(i * step)] for i in range(cap)})

    def assessment(self, learner_id: str) -> AdaptiveSession:
        try:
            return self._assessments[learner_id]
        except KeyError:
            raise KeyError(f"no active assessment for {learner_id!r}") from None

    def assessment_band(self, learner_id: str) -> str | None:
        """The self-reported band from this learner's diagnostic, if they took one."""
        sess = self._assessments.get(learner_id)
        return sess.band if sess is not None else None

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
        state = scale_velocity(state, speed)
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

    # ------------------------------------------------------- deadline calendar (claim C)
    def calendar_plan(
        self,
        learner_id: str,
        goals: Sequence[str],
        *,
        deadline: date,
        availability: Availability,
        start: date | None = None,
        time_budget_s: float | None = None,
        speed: float = 1.0,
    ) -> CalendarPlan:
        """Sequence the goals, then embed that plan on a real calendar so every
        goal skill is predicted at/above threshold on ``deadline`` - or report
        exactly why the date cannot be met."""
        start = start or date.today()
        if time_budget_s is None:
            weeks = max(1.0, (deadline - start).days / 7.0)
            time_budget_s = availability.weekly_minutes * 60.0 * weeks
        budget = time_budget_s
        plans = self.recommend(
            learner_id, goals, time_budget_s=budget, mode="sequence", speed=speed
        )
        plan = plans[0] if plans else Plan.infeasible("no plan")
        state = replace(self.ensure(learner_id, time_budget_s=budget), time_budget_s=budget)
        return schedule_on_calendar(
            self.kg,
            plan,
            state,
            list(goals),
            start=start,
            deadline=deadline,
            availability=availability,
        )

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
        # claim D: snapshot the learner's mastery of *everything else* before this
        # attempt, so the prerequisite-graph evidence sees "attempted c with / without a".
        snapshot = {c: state.decayed_mastery(c) for c in self.kg.concept_ids}
        for c in r.concepts:
            self.evidence.record(snapshot, c, attempt.correct)
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

    # ------------------------------------------- execution-verified practice loop
    def concept_id(self, bare: str) -> str | None:
        """This graph's id for a seed concept: the bare id in a seed graph, or
        ``domain.id`` in a role graph.  ``None`` when the graph doesn't have it."""
        if bare in self.kg.concepts:
            return bare
        domain = CONCEPT_DOMAIN.get(bare)
        cid = f"{domain}.{bare}" if domain else None
        return cid if cid in self.kg.concepts else None

    sql_concept = concept_id  # the SQL track's original name

    def practice_tasks(self) -> list[Task]:
        """The practice tasks whose concept exists in this graph - every domain."""
        return [t for t in ALL_TASKS if self.concept_id(t.concept) is not None]

    def submit_practice(
        self,
        learner_id: str,
        task_id: str,
        query: str,
        *,
        goals: Sequence[str] | None = None,
        minutes: float = 5.0,
        time_budget_s: float = _PRACTICE_BUDGET_S,
        attribute: bool = True,
    ) -> PracticeOutcome:
        """One turn of the closed loop:

        1. run the learner's SQL in the sandbox and grade it by its **result**;
        2. fingerprint a failure into the concepts it implicates;
        3. update the learner - the task's own concept through :meth:`observe`,
           and each **blamed** concept by a weighted BKT failure step (on a pass,
           the concepts the task also exercises get a weighted success step);
        4. record each blamed prerequisite as direct evidence on its edge
           (claim D) - including watched candidate edges, so a misconception
           that keeps surfacing under a concept it isn't linked to grows an edge;
        5. re-plan with anytime A* and pick the next task from the new plan.

        ``attribute=False`` is the outcome-only baseline: the submission is still
        graded, but the diagnosis is not acted on (steps 3-4 see only right / wrong).
        """
        task = BY_ID.get(task_id)
        if task is None:
            raise KeyError(f"unknown task {task_id!r}")
        target = self.concept_id(task.concept)
        if target is None:
            raise KeyError(f"task {task_id!r} is about {task.concept!r}, not in this graph")

        verdict = grade_task(task, query)
        result = verdict.result
        self.ensure(learner_id, time_budget_s=time_budget_s)
        blamed = {
            cid: w
            for c, w in verdict.blamed.items()
            if attribute and (cid := self.concept_id(c)) is not None and cid != target
        }
        touched = [target, *blamed]
        if verdict.correct:
            touched += [c for u in task.uses if (c := self.concept_id(u)) and c not in touched]
        before = {c: self._mastery(learner_id, c) for c in touched}

        state = self.observe(
            learner_id, Attempt(f"{target}:practice", verdict.correct, minutes * 60.0)
        ).copy()
        if verdict.correct:
            for c in touched[1:]:
                state.mastery[c] = _weighted_bkt(state.mastery.get(c, 0.0), True, 0.5)
        for c, w in blamed.items():
            state.mastery[c] = _weighted_bkt(state.mastery.get(c, 0.0), False, w)
        self.store.put(learner_id, state)

        evidence: list[tuple[str, str, float]] = []
        for c, w in blamed.items():
            belief = self.evidence.attribute(c, target, w)
            if belief is not None:
                evidence.append((c, target, round(belief.mean, 3)))

        if verdict.correct:
            self._solved.setdefault(learner_id, set()).add(task.id)
        # a blamed concept that is now below threshold becomes a repair goal, so
        # the re-plan routes through it even when the graph has no edge to it yet
        repair = [
            c for c, w in blamed.items() if w >= _REPAIR_MIN_WEIGHT and not state.is_mastered(c)
        ]
        open_repairs = self._repairs.setdefault(learner_id, set())
        open_repairs.update(repair)
        open_repairs.difference_update(c for c in list(open_repairs) if state.is_mastered(c))
        t0 = time.perf_counter()
        plan_goals = list(dict.fromkeys([*repair, *(goals or [target])]))
        plans = self.recommend(
            learner_id, plan_goals, time_budget_s=time_budget_s, mode="interactive"
        )
        replan_ms = (time.perf_counter() - t0) * 1e3
        plan = plans[0] if plans else Plan.infeasible("no plan")
        return PracticeOutcome(
            task_id=task.id,
            correct=verdict.correct,
            result=result,
            diagnoses=verdict.diagnoses,
            mastery={c: (before[c], round(state.mastery.get(c, 0.0), 3)) for c in touched},
            edge_evidence=tuple(evidence),
            plan=plan,
            next_task=(
                self._next_task(state, learner_id, list(plan.concepts))
                if verdict.correct
                else self._next_task(state, learner_id, repair, fallback=task.id)
            ),
            replan_ms=round(replan_ms, 2),
            graded=verdict,
        )

    def repairs(self, learner_id: str) -> frozenset[str]:
        """Concepts a practice diagnosis routed in as repairs, not yet mastered."""
        state = self.store.get(learner_id)
        open_repairs = self._repairs.get(learner_id, set())
        if state is not None:
            open_repairs.difference_update(c for c in list(open_repairs) if state.is_mastered(c))
        return frozenset(open_repairs)

    def _mastery(self, learner_id: str, concept: str) -> float:
        state = self.store.get(learner_id)
        return round(state.mastery.get(concept, 0.0), 3) if state else 0.0

    def next_practice_task(
        self, learner_id: str, goals: Sequence[str]
    ) -> tuple[str | None, list[str]]:
        """Where to start practising toward ``goals``: (first task on the plan,
        the plan's concept path)."""
        state = self.ensure(learner_id, time_budget_s=_PRACTICE_BUDGET_S)
        plans = self.recommend(
            learner_id, goals, time_budget_s=_PRACTICE_BUDGET_S, mode="interactive"
        )
        path = list(dict.fromkeys(plans[0].concepts)) if plans else []
        return self._next_task(state, learner_id, path), path

    def _next_task(
        self, state: LearnerState, learner_id: str, path: list[str], *, fallback: str | None = None
    ) -> str | None:
        """The first unsolved task for an unmastered concept on ``path``; else
        ``fallback``; else a solved task for a concept that still isn't mastered.

        After a failure ``path`` is just the repair concepts and ``fallback`` the
        failed task: repair the blamed prerequisite first, otherwise retry."""
        solved = self._solved.get(learner_id, set())
        open_path = [c for c in path if not state.is_mastered(c)]
        for c in open_path:
            for t in tasks_for(c):
                if t.id not in solved:
                    return t.id
        if fallback is not None:
            return fallback
        return next((t.id for c in open_path for t in tasks_for(c)), None)

    # ------------------------------------------------- self-healing graph (claim D)
    def graph_health(self) -> GraphHealthReport:
        """Dry run: what the accumulated trajectory evidence says about the graph."""
        _healed, report = self.evidence.heal(self.kg)
        return report

    def heal_graph(self) -> GraphHealthReport:
        """Apply the repairs and plan on the healed graph from now on."""
        healed, report = self.evidence.heal(self.kg)
        self.kg = healed
        return report

    # ------------------------------------------------------------- explain
    def explain(self, learner_id: str, resource_id: str) -> str:
        state = self.store.get(learner_id) or self.ensure(learner_id, time_budget_s=3600.0)
        return explain_step(self.kg, resource_id, self.kg.resources[resource_id].concepts[0], state)
