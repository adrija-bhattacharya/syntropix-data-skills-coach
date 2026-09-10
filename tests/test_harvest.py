"""Open-resource discovery: level estimation + snapshot-backed catalogue.

Network is disabled (``VELPO_HARVEST_OFFLINE``); the committed snapshot at
``harvest/data/algebra_catalogue.json`` is the fixture.
"""

from __future__ import annotations

import pytest

from curriculum import build_curriculum
from engine import Engine
from harvest.catalogue import _off_domain, _relevance, discover_catalogue
from harvest.level import estimate_level, flesch_kincaid_grade, jargon_density
from harvest.model import RawResource


def _res(**kw: object) -> RawResource:
    base: dict[str, object] = {
        "source": "wikipedia",
        "kind": "article",
        "title": "T",
        "url": "https://x/y",
        "summary": "",
    }
    base.update(kw)
    return RawResource(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------- level
def test_flesch_kincaid_rises_with_sentence_and_word_complexity() -> None:
    simple = "The cat sat. The dog ran. We had fun."
    dense = (
        "Notwithstanding the aforementioned considerations, the epistemological "
        "ramifications of the hypothesis necessitate a comprehensive reevaluation."
    )
    assert flesch_kincaid_grade(dense) > flesch_kincaid_grade(simple)


def test_jargon_density_counts_long_words() -> None:
    assert jargon_density("the big red dog") == 0.0
    assert jargon_density("polynomial factorisation determinant eigenvalue") > 0.8


def test_intro_titles_are_easier_than_advanced_ones() -> None:
    txt = "This resource covers the topic with worked examples and exercises for practice."
    easy = estimate_level(_res(title="Introduction to Fractions", summary=txt))
    hard = estimate_level(_res(title="Advanced Fractions: a rigorous treatment", summary=txt))
    assert easy.difficulty < hard.difficulty


def test_a_paper_starts_harder_than_an_encyclopedia_article() -> None:
    txt = "We study the spectral properties of the operator and prove a bound on its norm."
    paper = estimate_level(_res(source="arxiv", kind="paper", title="On norms", summary=txt))
    article = estimate_level(_res(source="wikipedia", kind="article", title="Norm", summary=txt))
    assert paper.difficulty > article.difficulty


def test_difficulty_is_clamped_to_the_1_5_scale() -> None:
    lvl = estimate_level(_res(title="x", summary="a b c d e f g h i j"))
    assert 1.0 <= lvl.difficulty <= 5.0


def test_youtube_quality_uses_like_ratio() -> None:
    hot = estimate_level(
        _res(
            source="youtube",
            kind="video",
            summary="tutorial " * 20,
            metadata={"views": 500_000, "likes": 25_000},
        )
    )
    cold = estimate_level(
        _res(
            source="youtube",
            kind="video",
            summary="tutorial " * 20,
            metadata={"views": 500_000, "likes": 50},
        )
    )
    assert hot.quality > cold.quality


# --------------------------------------------------------------- relevance
def test_relevance_gate_drops_a_keyword_collision() -> None:
    off = _res(title="LinearAccelerationSensor API", summary="a web sensor interface")
    assert _relevance("Linear equation", off) == 0.0


def test_relevance_gate_passes_the_canonical_article() -> None:
    canon = _res(title="Anything", summary="", metadata={"canonical": True})
    assert _relevance("Quadratic equation", canon) == 6.0


def test_off_domain_filter_rejects_programming_hits_for_math() -> None:
    assert _off_domain("math", _res(title="JavaScript/Functions", source="wikibooks"))
    assert not _off_domain("math", _res(title="Algebra/Functions", source="wikibooks"))


# --------------------------------------------------------------- catalogue
def test_discovered_catalogue_is_a_valid_plannable_graph() -> None:
    kg = discover_catalogue(build_curriculum(), snapshot="algebra")
    assert kg.concept_ids == build_curriculum().concept_ids
    for c in kg.concept_ids:
        assert kg.resources_for(c), f"{c} has no resource"
    real = [r for r in kg.resources.values() if r.source]
    assert len(real) > 20
    assert {r.source for r in real} >= {"wikipedia"}
    assert all(r.url.startswith("http") for r in real)

    plan = Engine(kg).recommend("u", ["quadratics"], time_budget_s=12000, mode="sequence")[0]
    assert plan.feasible and plan.steps
    # a real link rides along on each step
    assert any(kg.resources[s].url for s in plan.steps)


def test_snapshot_resources_span_a_difficulty_range() -> None:
    kg = discover_catalogue(build_curriculum(), snapshot="algebra")
    diffs = {r.difficulty for r in kg.resources.values() if r.source}
    assert max(diffs) - min(diffs) >= 1.5  # the sequencing DP has a real easy/hard choice


@pytest.mark.parametrize("cid", ["integers", "linear_eq", "functions", "word_problems"])
def test_every_seed_concept_got_real_resources(cid: str) -> None:
    kg = discover_catalogue(build_curriculum(), snapshot="algebra")
    assert any(kg.resources[r].source for r in kg.resources_for(cid))
