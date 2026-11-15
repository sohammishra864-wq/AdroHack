from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from PIL import Image


@dataclass
class LocResult:
    heatmap: np.ndarray             # H×W in [0, 1], 1 = manipulated
    reliability: np.ndarray | None  # H×W in [0, 1], where the heatmap can be trusted
    integrity: float                # image-level 0 authentic … 1 manipulated


class Localizer(Protocol):
    name: str

    def warm(self) -> None: ...

    def __call__(self, rgb: Image.Image) -> LocResult: ...
