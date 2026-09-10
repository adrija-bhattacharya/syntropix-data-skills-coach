"""Open-resource discovery: turn a concept into real, level-matched, open
learning resources (articles, books, videos, courses, papers) instead of a
hand-authored synthetic catalogue.

    from harvest import discover_catalogue
    kg = discover_catalogue(build_curriculum())      # -> KnowledgeGraph with real Resources
"""

from harvest.catalogue import algebra_catalogue, discover_catalogue, discover_for_concept
from harvest.level import estimate_level
from harvest.model import RawResource

__all__ = [
    "RawResource",
    "algebra_catalogue",
    "discover_catalogue",
    "discover_for_concept",
    "estimate_level",
]
