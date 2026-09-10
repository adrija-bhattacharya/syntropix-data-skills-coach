"""The common shape every source is normalised to before ranking / level-estimation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class RawResource:
    source: str  # "wikipedia" | "wikibooks" | "mdn" | "mit_learn" | "youtube" | "arxiv"
    kind: str  # "article" | "book" | "docs" | "course" | "video" | "paper"
    title: str
    url: str
    summary: str = ""  # abstract / extract / description - the text level-estimation reads
    minutes: float = 12.0  # estimated study time
    metadata: dict[str, Any] = field(default_factory=dict)

    def key(self) -> str:
        return self.url.split("#")[0].rstrip("/").lower()
