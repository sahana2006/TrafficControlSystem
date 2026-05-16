"""
Multi-controller comparison graphs for research publications.
Loads accumulated CSV history from results/csv/.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

import config
from visualization.plots import CONTROLLER_COLORS, PlotGenerator


def load_metrics_history(csv_dir: Path | None = None) -> list[dict]:
    csv_dir = csv_dir or config.CSV_DIR
    path = csv_dir / "metrics_summary.csv"
    if not path.exists():
        return []
    df = pd.read_csv(path)
    return df.to_dict(orient="records")


def compare_controllers(output_dir: Path | None = None) -> None:
    history = load_metrics_history()
    if not history:
        return
    gen = PlotGenerator(output_dir)
    latest = history[-1]
    ts = pd.read_csv(config.CSV_DIR / "metrics_timeseries.csv") if (config.CSV_DIR / "metrics_timeseries.csv").exists() else pd.DataFrame()
    gen.generate_all(latest, ts, history)
