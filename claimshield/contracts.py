"""Data contracts shared by every lane (README § Contracts)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Tier = Literal["fast", "deep", "doc", "identity", "claim"]
Band = Literal["LOW", "MEDIUM", "HIGH", "UNCERTAIN"]


@dataclass
class Signal:
    name: str
    score: float | None      # 0 authentic … 1 manipulated; None if abstained / n.a.
    confidence: float        # 0..1
    reason: str              # one sentence an adjuster understands
    evidence: dict = field(default_factory=dict)
    abstained: bool = False  # quality gate fired
    applicable: bool = True  # False → "not applicable: PNG has no JPEG tables"
    tier: Tier = "fast"


@dataclass
class Region:
    box: tuple[int, int, int, int]
    area_frac: float
    signals: dict[str, float]    # which signals fired inside the box
    reason: str
    stage: int                   # 1 = fast, 2 = AE-corroborated


@dataclass
class ClaimScore:
    image_score: float | None
    document_score: float | None
    identity_score: float | None
    overall: float
    band: Band
    waterfall: list[tuple[str, float]]
    regions: list[Region]
    signals: list[Signal]
    pending_deep: bool = False   # True until the deep tier lands
