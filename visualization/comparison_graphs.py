"""
Rule-Based vs DQN comparison plots for research output.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config

CONTROLLERS = ["rule_based", "dqn"]
COLORS = {"rule_based": "#2563eb", "dqn": "#dc2626"}
LABELS = {"rule_based": "Rule-Based", "dqn": "DQN"}


def _style(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.6)
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(fontsize=9)


def load_comparison_df() -> pd.DataFrame:
    path = config.COMPARISON_CSV
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def append_comparison_row(summary: dict) -> None:
    row = {
        "controller_type": summary.get("controller_type", summary.get("controller")),
        "traffic_profile": summary.get("traffic_profile", config.TRAFFIC_PROFILE),
        "EVTT": summary.get("EVTT", 0),
        "EVSF": summary.get("EVSF", 0),
        "GWSR": summary.get("GWSR", 0),
        "CVDI": summary.get("CVDI", 0),
        "ICP": summary.get("ICP", 0),
        "total_reward": summary.get("total_reward", summary.get("dqn_total_reward", 0)),
    }
    df = pd.DataFrame([row])
    if config.COMPARISON_CSV.exists():
        existing = pd.read_csv(config.COMPARISON_CSV)
        df = pd.concat([existing, df], ignore_index=True)
    config.ensure_dirs()
    df.to_csv(config.COMPARISON_CSV, index=False)


class ComparisonPlotGenerator:
    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or config.PLOTS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        try:
            plt.style.use("seaborn-v0_8-whitegrid")
        except OSError:
            plt.style.use("ggplot")

    def _save(self, fig: plt.Figure, name: str) -> Path:
        p = self.output_dir / name
        fig.savefig(p, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        return p

    def generate_all(
        self,
        comparison_df: pd.DataFrame,
        dqn_rewards: list[float] | None = None,
        rule_ts: pd.DataFrame | None = None,
        dqn_ts: pd.DataFrame | None = None,
    ) -> list[Path]:
        paths = [
            self.plot_evtt_comparison(comparison_df),
            self.plot_evsf_comparison(comparison_df),
            self.plot_queue_comparison(rule_ts, dqn_ts),
            self.plot_gwsr_comparison(comparison_df),
            self.plot_cvdi_comparison(comparison_df),
            self.plot_reward_convergence(dqn_rewards),
            self.plot_congestion_heatmap(comparison_df),
            self.plot_scalability_placeholder(),
        ]
        return paths

    def plot_evtt_comparison(self, df: pd.DataFrame) -> Path:
        fig, ax = plt.subplots(figsize=(8, 5))
        for ctrl in CONTROLLERS:
            sub = df[df["controller_type"] == ctrl]
            val = float(sub["EVTT"].iloc[-1]) if len(sub) else np.nan
            if not np.isnan(val):
                ax.bar(LABELS[ctrl], val, color=COLORS[ctrl], edgecolor="black", width=0.5)
        _style(ax, "EVTT Comparison: Rule-Based vs DQN", "Controller", "EV Travel Time (s)")
        return self._save(fig, "compare_evtt.png")

    def plot_evsf_comparison(self, df: pd.DataFrame) -> Path:
        fig, ax = plt.subplots(figsize=(8, 5))
        x, h, c = [], [], []
        for ctrl in CONTROLLERS:
            sub = df[df["controller_type"] == ctrl]
            if len(sub):
                x.append(LABELS[ctrl])
                h.append(float(sub["EVSF"].iloc[-1]))
                c.append(COLORS[ctrl])
        ax.bar(x, h, color=c, edgecolor="black")
        _style(ax, "EV Stop Frequency Comparison", "Controller", "Stop Count")
        return self._save(fig, "compare_evsf.png")

    def plot_queue_comparison(
        self, rule_ts: pd.DataFrame | None, dqn_ts: pd.DataFrame | None
    ) -> Path:
        fig, ax = plt.subplots(figsize=(10, 5))
        if rule_ts is not None and len(rule_ts) and "avg_queue" in rule_ts.columns:
            ax.plot(rule_ts["time"], rule_ts["avg_queue"], color=COLORS["rule_based"],
                    lw=1.8, label=LABELS["rule_based"])
        if dqn_ts is not None and len(dqn_ts) and "avg_queue" in dqn_ts.columns:
            ax.plot(dqn_ts["time"], dqn_ts["avg_queue"], color=COLORS["dqn"],
                    lw=1.8, label=LABELS["dqn"])
        _style(ax, "Queue Length Comparison", "Simulation Time (s)", "Average Queue")
        return self._save(fig, "compare_queue.png")

    def plot_gwsr_comparison(self, df: pd.DataFrame) -> Path:
        fig, ax = plt.subplots(figsize=(8, 5))
        x, h, c = [], [], []
        for ctrl in CONTROLLERS:
            sub = df[df["controller_type"] == ctrl]
            if len(sub):
                x.append(LABELS[ctrl])
                h.append(float(sub["GWSR"].iloc[-1]))
                c.append(COLORS[ctrl])
        ax.bar(x, h, color=c, edgecolor="black")
        ax.set_ylim(0, 1.05)
        _style(ax, "Green-Wave Success Ratio Comparison", "Controller", "GWSR")
        return self._save(fig, "compare_gwsr.png")

    def plot_cvdi_comparison(self, df: pd.DataFrame) -> Path:
        fig, ax = plt.subplots(figsize=(8, 5))
        x, h, c = [], [], []
        for ctrl in CONTROLLERS:
            sub = df[df["controller_type"] == ctrl]
            if len(sub):
                x.append(LABELS[ctrl])
                h.append(float(sub["CVDI"].iloc[-1]))
                c.append(COLORS[ctrl])
        ax.bar(x, h, color=c, edgecolor="black")
        _style(ax, "Civilian Delay Index Comparison", "Controller", "CVDI")
        return self._save(fig, "compare_cvdi.png")

    def plot_reward_convergence(self, rewards: list[float] | None) -> Path:
        fig, ax = plt.subplots(figsize=(9, 5))
        if rewards:
            ax.plot(range(1, len(rewards) + 1), rewards, color=COLORS["dqn"],
                    marker="o", lw=2, label="DQN episode reward")
            if len(rewards) > 5:
                w = min(5, len(rewards))
                smooth = pd.Series(rewards).rolling(w, min_periods=1).mean()
                ax.plot(range(1, len(smooth) + 1), smooth, color="#9333ea",
                        ls="--", label=f"Moving avg (w={w})")
        else:
            ax.text(0.5, 0.5, "Run DQN training to populate\nreward convergence",
                    ha="center", va="center", transform=ax.transAxes)
        _style(ax, "DQN Reward Convergence", "Training Step / Episode", "Cumulative Reward")
        return self._save(fig, "compare_reward_convergence.png")

    def plot_congestion_heatmap(self, df: pd.DataFrame) -> Path:
        from visualization.heatmaps import congestion_heatmap_array
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        for i, ctrl in enumerate(CONTROLLERS):
            sub = df[df["controller_type"] == ctrl]
            base = float(sub["ICP"].iloc[-1]) if len(sub) else 0.05
            data = congestion_heatmap_array(config.GRID_ROWS, config.GRID_COLS, base)
            im = axes[i].imshow(data, cmap="YlOrRd", origin="lower")
            axes[i].set_title(f"{LABELS[ctrl]} Congestion")
            plt.colorbar(im, ax=axes[i], fraction=0.046)
        fig.suptitle("Congestion Heatmap Comparison", fontweight="bold")
        fig.tight_layout()
        return self._save(fig, "compare_congestion.png")

    def plot_scalability_placeholder(self) -> Path:
        fig, ax = plt.subplots(figsize=(8, 5))
        grids = ["4x4", "6x6", "7x28"]
        rb = [1.0, np.nan, np.nan]
        dqn = [0.95, np.nan, np.nan]
        x = np.arange(len(grids))
        w = 0.35
        ax.bar(x - w / 2, rb, w, label=LABELS["rule_based"], color=COLORS["rule_based"])
        ax.bar(x + w / 2, dqn, w, label=LABELS["dqn"], color=COLORS["dqn"])
        ax.set_xticks(x)
        ax.set_xticklabels(grids)
        _style(ax, "Scalability Placeholder (normalized EVTT)", "Grid Size", "Relative Performance")
        return self._save(fig, "compare_scalability.png")
