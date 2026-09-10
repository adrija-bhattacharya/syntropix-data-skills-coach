"""The curated resource library + profile -> resource recommendation table."""

from __future__ import annotations

import re

from data_resources import (
    PROFILE_RECOMMENDATIONS,
    RESOURCES,
    LearnResource,
    recommend_resources,
    resource_by_id,
)

_YT = re.compile(r"^https://www\.youtube\.com/(watch\?v=|playlist\?list=|@)")


# --------------------------------------------------------------------------- #
def test_library_is_well_formed() -> None:
    ids = [r.id for r in RESOURCES]
    assert len(ids) == len(set(ids))  # unique
    for r in RESOURCES:
        assert isinstance(r, LearnResource)
        assert r.url.startswith("https://")
        assert 1 <= r.level <= 5
        assert r.bands and set(r.bands) <= {"beginner", "intermediate", "advanced"}
        assert r.domains
        if r.kind in ("video", "playlist", "channel"):
            assert _YT.match(r.url), r.url  # real YouTube links only


def test_profile_table_references_only_real_resources() -> None:
    for key, rids in PROFILE_RECOMMENDATIONS.items():
        role_or_domain, band = key.rsplit(":", 1)
        assert band in {"beginner", "intermediate", "advanced"}
        assert role_or_domain
        for rid in rids:
            assert resource_by_id(rid) is not None, f"{key} -> unknown {rid}"


def test_data_analyst_profiles_are_covered_for_every_band() -> None:
    for band in ("beginner", "intermediate", "advanced"):
        assert f"data analyst:{band}" in PROFILE_RECOMMENDATIONS


# --------------------------------------------------------------------------- #
def test_recommendation_starts_from_the_profile_labels() -> None:
    labelled = PROFILE_RECOMMENDATIONS["data analyst:beginner"]
    rec = recommend_resources(
        profile="data analyst",
        band="beginner",
        concepts={"sql.select_from", "sql.group_by"},
        concept_names={"sql.select_from": "SELECT", "sql.group_by": "GROUP BY"},
        domains={"sql"},
        limit=4,
    )
    ids = [r.id for r in rec]
    assert ids[0] == labelled[0]  # the hand-picked first choice leads
    assert any("youtube.com" in r.url for r in rec)


def test_band_changes_what_is_recommended() -> None:
    def _rec(band: str) -> list[str]:
        return [
            r.id
            for r in recommend_resources(
                profile="stats",
                band=band,
                concepts={"stats.hypothesis_testing"},
                concept_names={"stats.hypothesis_testing": "Hypothesis testing"},
                domains={"stats"},
                limit=3,
            )
        ]

    beg, adv = _rec("beginner"), _rec("advanced")
    assert beg != adv  # a beginner and an advanced learner are steered differently
    assert beg[0] == "statquest_stats" and adv[0] == "statquest_channel"


def test_a_watchable_resource_is_always_offered() -> None:
    rec = recommend_resources(
        profile="nonexistent-domain",
        band="intermediate",
        concepts={"xyz.some_obscure_skill"},
        concept_names={"xyz.some_obscure_skill": "Some obscure skill"},
        domains={"xyz"},
        limit=3,
    )
    assert rec and any(r.kind in ("video", "playlist") for r in rec)


def test_search_fallback_when_only_docs_would_match() -> None:
    from data_resources import _search_resource

    r = _search_resource("Window functions", "beginner", "sql")
    assert r.url.startswith("https://www.youtube.com/results?search_query=")
    assert "Window+functions" in r.url and r.kind == "video"
