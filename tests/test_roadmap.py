"""The personalised roadmap: phases, pace, certifications, finish estimate."""

from __future__ import annotations

from datetime import date, timedelta

from certifications import Certification, certifications_for
from domains import resolve
from model.learner import LearnerState
from roadmap import build_roadmap


def _state(kg_ids: list[str], *, velocity: float = 1.0) -> LearnerState:
    st = LearnerState.cold_start(kg_ids, time_budget_s=3600)
    for c in st.velocity:
        st.velocity[c] = velocity
    return st


# --------------------------------------------------------------------------- #
def test_seed_goal_covers_the_whole_track() -> None:
    r = resolve("learn sql")
    rm = build_roadmap(r.kg, r, _state(r.kg.concept_ids), weekly_hours=5)
    covered = {c for p in rm.phases for c in p.concept_ids}
    assert covered == set(r.kg.concept_ids)  # not just the closure of one concept
    assert rm.phases[0].start_week == 0.0
    assert rm.total_hours > 20  # a real estimate, not the raw synthetic minutes
    assert rm.phases == tuple(sorted(rm.phases, key=lambda p: p.start_week))


def test_pace_scales_the_estimate() -> None:
    r = resolve("learn python")
    slow = build_roadmap(r.kg, r, _state(r.kg.concept_ids, velocity=0.4), weekly_hours=5)
    fast = build_roadmap(r.kg, r, _state(r.kg.concept_ids, velocity=3.0), weekly_hours=5)
    assert slow.pace == "deliberate" and fast.pace == "fast"
    assert slow.total_hours > fast.total_hours


def test_role_roadmap_groups_by_domain_and_places_certs() -> None:
    r = resolve("become a data analyst")
    rm = build_roadmap(r.kg, r, _state(r.kg.concept_ids), weekly_hours=6, band="beginner")
    assert rm.role == "data analyst"
    assert rm.band == "beginner"
    assert len(rm.phases) >= 3
    assert {"SQL", "pandas & NumPy"} <= {p.title for p in rm.phases}
    # every roadmap surfaces profile-matched resources with real links
    assert rm.recommended and all(str(v["url"]).startswith("https://") for v in rm.recommended)
    assert any(p.videos for p in rm.phases)
    yt = [v for v in rm.recommended if "youtube.com" in str(v["url"])]
    assert yt  # at least one YouTube pick for a beginner analyst
    all_phase_certs = {c.id for p in rm.phases for c in p.certifications}
    assert all_phase_certs  # at least one certification is anchored to a phase
    # every phase certification is genuinely covered by that point
    running: set[str] = set()
    for p in rm.phases:
        running.update(p.concept_ids)
        for cert in p.certifications:
            assert cert.coverage(running) >= 0.6


def test_already_mastered_skills_are_skipped() -> None:
    r = resolve("learn sql")
    st = _state(r.kg.concept_ids)
    for c in ("select_from", "where", "order_limit"):
        st.mastery[c] = 0.95
    rm = build_roadmap(r.kg, r, st, weekly_hours=5)
    assert set(rm.already_have) >= {"SELECT ... FROM", "WHERE & comparison operators"}
    baseline = build_roadmap(r.kg, r, _state(r.kg.concept_ids), weekly_hours=5)
    assert rm.total_hours < baseline.total_hours


def test_deadline_sets_on_track_flag() -> None:
    r = resolve("learn sql")
    tight = build_roadmap(
        r.kg, r, _state(r.kg.concept_ids), weekly_hours=2, deadline=date.today() + timedelta(days=7)
    )
    roomy = build_roadmap(
        r.kg,
        r,
        _state(r.kg.concept_ids),
        weekly_hours=10,
        deadline=date.today() + timedelta(days=400),
    )
    assert tight.on_track is False
    assert roomy.on_track is True


def test_finish_estimate_is_present_and_future() -> None:
    r = resolve("learn sql")
    rm = build_roadmap(r.kg, r, _state(r.kg.concept_ids), weekly_hours=5)
    assert rm.finish_estimate is not None
    assert rm.finish_estimate > date.today().isoformat()


# --------------------------------------------------------------------------- #
def test_certifications_catalogue_is_well_formed() -> None:
    sql_certs = certifications_for({"sql"})
    assert sql_certs and all(isinstance(c, Certification) for c in sql_certs)
    for c in sql_certs:
        assert c.url.startswith("https://")
        assert c.skills and 0.0 <= c.coverage({"select_from", "where"}) <= 1.0
        assert c.level in ("entry", "associate", "professional")
    # entry-level listed before professional
    levels = [c.level for c in certifications_for({"sql", "python", "stats"})]
    assert levels.index("entry") < levels.index("professional")


def test_coverage_matches_prefixed_and_bare_ids() -> None:
    cert = certifications_for({"sql"})[0]
    bare = cert.coverage(set(cert.skills))
    prefixed = cert.coverage({f"sql.{s}" for s in cert.skills})
    assert bare == prefixed == 1.0
