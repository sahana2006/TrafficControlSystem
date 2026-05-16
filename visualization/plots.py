"""
Research-quality plots — saved to results/plots/.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config
from visualization.heatmaps import congestion_heatmap_array


def _style_axes(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title, fontsize=13, fontweight="bold", pad=10)
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.grid(True, linestyle="--", alpha=0.6)


def _maybe_legend(ax) -> None:
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(loc="best", fontsize=9)


class PlotGenerator:
    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or config.PLOTS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        try:
            plt.style.use("seaborn-v0_8-whitegrid")
        except OSError:
            plt.style.use("ggplot")
        plt.rcParams.update({
            "figure.dpi": 120,
            "savefig.dpi": 180,
            "font.size": 10,
        })

    def _save(self, fig: plt.Figure, name: str) -> Path:
        path = self.output_dir / name
        fig.savefig(path, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        return path

    def generate_required(
        self,
        summary: dict,
        timeseries: pd.DataFrame,
        stream: pd.DataFrame | None = None,
    ) -> list[Path]:
        stream = stream if stream is not None and len(stream) else None
        return [
            self.plot_evtt(summary, stream),
            self.plot_queue(timeseries, stream),
            self.plot_congestion(summary, timeseries),
            self.plot_evsf(summary, stream),
            self.plot_gwsr(summary, stream),
        ]

    def plot_evtt(self, summary: dict, stream: pd.DataFrame | None) -> Path:
        fig, ax = plt.subplots(figsize=(9, 5))

        if stream is not None and "evtt" in stream.columns and "timestamp" in stream.columns:
            t = pd.to_numeric(stream["timestamp"], errors="coerce")
            evtt = pd.to_numeric(stream["evtt"], errors="coerce")
            mask = evtt > 0
            if mask.any():
                ax.plot(t[mask], evtt[mask], color="#dc2626", lw=2, label="EV travel time (running)")
                ax.axhline(float(summary.get("EVTT", evtt[mask].iloc[-1])), color="#2563eb", ls="--",
                           label=f"Final EVTT = {summary.get('EVTT', 0):.1f}s")
        else:
            ax.bar(
                [config.TRAFFIC_PROFILE],
                [summary.get("EVTT", 0)],
                color="#dc2626",
                edgecolor="black",
                width=0.5,
                label="EVTT",
            )

        _style_axes(ax, "Emergency Vehicle Travel Time (EVTT)", "Simulation Time (s)", "Travel Time (s)")
        _maybe_legend(ax)
        return self._save(fig, "evtt.png")

    def plot_queue(self, timeseries: pd.DataFrame, stream: pd.DataFrame | None) -> Path:
        fig, ax = plt.subplots(figsize=(10, 5))

        if stream is not None and "queue_length" in stream.columns:
            t = pd.to_numeric(stream["timestamp"], errors="coerce")
            q = pd.to_numeric(stream["queue_length"], errors="coerce")
            ax.plot(t, q, color="#2563eb", lw=1.8, label="Avg queue (stream)")
        elif len(timeseries) and "avg_queue" in timeseries.columns:
            ax.plot(timeseries["time"], timeseries["avg_queue"], color="#2563eb", lw=1.8, label="Avg queue")

        _style_axes(ax, "Queue Length Over Time", "Simulation Time (s)", "Average Queue Length (veh)")
        _maybe_legend(ax)
        return self._save(fig, "queue.png")

    def plot_congestion(self, summary: dict, timeseries: pd.DataFrame) -> Path:
        fig, ax = plt.subplots(figsize=(8, 7))
        base = float(summary.get("ICP", 0.05))
        if len(timeseries) and "icp" in timeseries.columns:
            base = max(base, float(timeseries["icp"].mean()))

        data = congestion_heatmap_array(config.GRID_ROWS, config.GRID_COLS, base)
        im = ax.imshow(data, cmap="YlOrRd", aspect="equal", origin="lower")
        ax.set_xticks(range(config.GRID_COLS))
        ax.set_yticks(range(config.GRID_ROWS))
        ax.set_xticklabels([f"Col {i}" for i in range(config.GRID_COLS)])
        ax.set_yticklabels([f"Row {i}" for i in range(config.GRID_ROWS)])
        cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label("Congestion pressure (ICP)", fontsize=10)
        _style_axes(ax, "Intersection Congestion Heatmap", "Column", "Row")
        return self._save(fig, "congestion.png")

    def plot_evsf(self, summary: dict, stream: pd.DataFrame | None) -> Path:
        fig, ax = plt.subplots(figsize=(9, 5))

        if stream is not None and "evsf" in stream.columns and "timestamp" in stream.columns:
            t = pd.to_numeric(stream["timestamp"], errors="coerce")
            stops = pd.to_numeric(stream["evsf"], errors="coerce")
            mask = t >= config.EV_DEPART_TIME_S
            ax.step(t[mask], stops[mask], where="post", color="#dc2626", lw=2, label="Cumulative stops")
            ax.axhline(float(summary.get("EVSF", stops[mask].iloc[-1] if mask.any() else 0)),
                       color="#64748b", ls="--", label=f"Final EVSF = {summary.get('EVSF', 0):.0f}")
        else:
            ax.bar(["EV Stops"], [summary.get("EVSF", 0)], color="#dc2626", edgecolor="black")

        _style_axes(ax, "Emergency Vehicle Stop Frequency (EVSF)", "Simulation Time (s)", "Stop Count")
        _maybe_legend(ax)
        return self._save(fig, "evsf.png")

    def plot_gwsr(self, summary: dict, stream: pd.DataFrame | None) -> Path:
        fig, ax = plt.subplots(figsize=(9, 5))
        final = float(summary.get("GWSR", 0))

        if stream is not None and "gwsr" in stream.columns and "timestamp" in stream.columns:
            t = pd.to_numeric(stream["timestamp"], errors="coerce")
            g = pd.to_numeric(stream["gwsr"], errors="coerce")
            mask = (t >= config.EV_DEPART_TIME_S) & (g > 0)
            if mask.any():
                ax.plot(t[mask], g[mask], color="#16a34a", lw=2, marker=".", ms=4, label="GWSR (running)")
        ax.axhline(final, color="#2563eb", ls="--", lw=1.5, label=f"Final GWSR = {final:.2%}")

        ax.set_ylim(-0.05, 1.05)
        _style_axes(ax, "Green-Wave Success Ratio (GWSR)", "Simulation Time (s)", "Success Ratio")
        _maybe_legend(ax)
        return self._save(fig, "gwsr.png")
