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


def test_speed_knob_rescales_the_same_learner() -> None:
    """ "Take it slow" / "move fast" (N2) must move the roadmap even for a
    learner whose *measured* velocity alone would read as "steady" - it is the
    same manual knob the sequenced study plan already respects."""
    r = resolve("learn python")
    baseline = _state(r.kg.concept_ids, velocity=1.0)
    slow = build_roadmap(r.kg, r, baseline, weekly_hours=5, speed=0.45)
    normal = build_roadmap(r.kg, r, baseline, weekly_hours=5, speed=1.0)
    fast = build_roadmap(r.kg, r, baseline, weekly_hours=5, speed=3.0)

    assert slow.pace == "deliberate"
    assert fast.pace == "fast"
    assert slow.total_hours > normal.total_hours > fast.total_hours
    assert slow.total_weeks > normal.total_weeks > fast.total_weeks
    assert slow.finish_estimate is not None and fast.finish_estimate is not None
    assert slow.finish_estimate > fast.finish_estimate
    # the input state itself is untouched (build_roadmap must not mutate it)
    assert all(v == 1.0 for v in baseline.velocity.values())


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
_CERT_HOSTS = (
    "coursera.org",
    "learn.microsoft.com",
    "freecodecamp.org",
    "kaggle.com",
    "hackerrank.com",
    "tableau.com",
    "github.com",
)


def test_certifications_catalogue_is_well_formed() -> None:
    from certifications import CERTIFICATIONS

    ids = [c.id for c in CERTIFICATIONS]
    assert len(ids) == len(set(ids))
    for c in CERTIFICATIONS:
        assert isinstance(c, Certification)
        assert c.url.startswith("https://")
        assert any(h in c.url for h in _CERT_HOSTS), c.url
        assert c.skills and c.domains
        assert c.level in ("entry", "associate", "professional")

    sql_certs = certifications_for({"sql"})
    assert sql_certs and 0.0 <= sql_certs[0].coverage({"select_from", "where"}) <= 1.0
    # entry before professional, and free before paid within a level
    seq = certifications_for({"sql", "python", "stats"})
    levels = [c.level for c in seq]
    assert levels.index("entry") < levels.index("professional")
    entry = [c for c in seq if c.level == "entry"]
    assert [c.free for c in entry] == sorted((c.free for c in entry), reverse=True)


def test_free_skill_verifications_are_present() -> None:
    ids = {c.id for c in certifications_for({"sql", "python", "dsa_python"})}
    assert {"hackerrank_sql", "hackerrank_python", "fcc_relational_db"} <= ids
    # HackerRank / PL-300 / Coursera all represented
    provs = {c.provider for c in certifications_for({"sql", "dataviz", "stats"})}
    assert "HackerRank" in provs and "Microsoft" in provs
    assert any("Coursera" in p for p in provs)


def test_coverage_matches_prefixed_and_bare_ids() -> None:
    cert = certifications_for({"sql"})[0]
    bare = cert.coverage(set(cert.skills))
    prefixed = cert.coverage({f"sql.{s}" for s in cert.skills})
    assert bare == prefixed == 1.0
