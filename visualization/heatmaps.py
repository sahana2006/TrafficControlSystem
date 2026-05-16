"""Congestion heatmap utilities."""
from __future__ import annotations

import numpy as np


def congestion_heatmap_array(rows: int, cols: int, base_pressure: float) -> np.ndarray:
    """Build intersection pressure grid with gradient from network center."""
    data = np.zeros((rows, cols))
    cx, cy = (cols - 1) / 2, (rows - 1) / 2
    for j in range(rows):
        for i in range(cols):
            dist = ((i - cx) ** 2 + (j - cy) ** 2) ** 0.5
            data[j, i] = base_pressure * (1.0 + 0.3 * dist / max(cx, cy, 1))
    return data
