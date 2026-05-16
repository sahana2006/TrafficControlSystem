"""
Metrics collection with continuous CSV streaming during simulation.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pandas as pd
import traci

import config
from environment.traci_utils import next_tls
from metrics import cvdi, evsf, evtt, gwsr, icp, sas, tre

STREAM_COLUMNS = [
    "timestamp",
    "controller_type",
    "evtt",
    "evsf",
    "queue_length",
    "gwsr",
    "cvdi",
    "reward",
]


class MetricsCollector:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._cumulative_reward = 0.0
        self._step_reward = 0.0
        self.timeseries: list[dict[str, Any]] = []
        self.decisions: list[str] = []
        self.ev_stops: dict[str, int] = {}
        self.ev_was_stopped: dict[str, bool] = {}
        self.gwsr_green = 0
        self.gwsr_total = 0
        self.civilian_waits: list[float] = []
        self.recovery_series: list[tuple[float, float]] = []
        self._summary: dict[str, Any] = {}
        self._ev_departure: float | None = None
        self._step_reward = 0.0
        self._cumulative_reward = 0.0
        self._stream_path = config.METRICS_CSV
        self._init_stream_csv()

    def reset_cumulative_reward(self) -> None:
        self._cumulative_reward = 0.0

    def _init_stream_csv(self) -> None:
        config.ensure_dirs()
        with open(self._stream_path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(STREAM_COLUMNS)

    def _append_stream_row(self, row: dict[str, Any]) -> None:
        with open(self._stream_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([row.get(c, "") for c in STREAM_COLUMNS])

    def record_step(
        self,
        sim_time: float,
        intersections: dict,
        evs: list,
        controller: Any,
    ) -> None:
        total_q = sum(ist.queue_length for ist in intersections.values())
        avg_q = total_q / max(len(intersections), 1)
        L = config.DEFAULT_LANE_LENGTH_M * max(len(intersections), 1)
        icp_val = icp.compute_icp(total_q, L)

        ev_speed = 0.0
        ev_pos_str = ""
        evtt_run = 0.0
        evsf_run = 0

        ev_id = config.EV_VEHICLE_ID
        if ev_id in traci.vehicle.getIDList():
            if self._ev_departure is None:
                self._ev_departure = sim_time
            ev_speed = traci.vehicle.getSpeed(ev_id)
            p = traci.vehicle.getPosition(ev_id)
            ev_pos_str = f"{p[0]:.1f},{p[1]:.1f}"
            evtt_run = sim_time - self._ev_departure

            stopped = traci.vehicle.getSpeed(ev_id) < 0.1 and traci.vehicle.getWaitingTime(ev_id) > 0.5
            if stopped:
                if not self.ev_was_stopped.get(ev_id, False):
                    self.ev_stops[ev_id] = self.ev_stops.get(ev_id, 0) + 1
                self.ev_was_stopped[ev_id] = True
            else:
                self.ev_was_stopped[ev_id] = False
            evsf_run = self.ev_stops.get(ev_id, 0)

            info = next_tls(ev_id)
            if info:
                self.gwsr_total += 1
                tls_id, _dist, tls_state = info
                if "G" in tls_state or "g" in tls_state:
                    self.gwsr_green += 1
                else:
                    try:
                        state = traci.trafficlight.getRedYellowGreenState(tls_id)
                        if "G" in state or "g" in state:
                            self.gwsr_green += 1
                    except traci.TraCIException:
                        pass

        for ev in evs:
            if ev.vehicle_id != ev_id:
                if ev.stopped and not self.ev_was_stopped.get(ev.vehicle_id, False):
                    self.ev_stops[ev.vehicle_id] = self.ev_stops.get(ev.vehicle_id, 0) + 1
                self.ev_was_stopped[ev.vehicle_id] = ev.stopped

        for vid in traci.vehicle.getIDList():
            try:
                if traci.vehicle.getTypeID(vid) != config.EV_TYPE_ID:
                    self.civilian_waits.append(traci.vehicle.getWaitingTime(vid))
            except traci.TraCIException:
                pass

        gwsr_run = gwsr.compute_gwsr(self.gwsr_green, self.gwsr_total)
        cvdi_run = cvdi.compute_cvdi(self.civilian_waits[-200:] if self.civilian_waits else [])

        sas_val = controller.sas if controller and hasattr(controller, "sas") else 0.0
        self.timeseries.append({
            "time": sim_time,
            "avg_queue": avg_q,
            "total_queue": total_q,
            "icp": icp_val,
            "sas": sas_val,
            "ev_count": len(evs),
            "ev_speed": ev_speed,
            "gwsr": gwsr_run,
            "cvdi": cvdi_run,
        })

        self._append_stream_row({
            "timestamp": f"{sim_time:.1f}",
            "controller_type": config.ACTIVE_CONTROLLER,
            "evtt": f"{evtt_run:.1f}",
            "evsf": str(evsf_run),
            "queue_length": f"{avg_q:.2f}",
            "gwsr": f"{gwsr_run:.4f}",
            "cvdi": f"{cvdi_run:.4f}",
            "reward": f"{self._cumulative_reward:.4f}",
        })
        self._step_reward = 0.0

    def record_reward(self, reward: float) -> None:
        self._step_reward += reward
        self._cumulative_reward += reward

    def record_decision(self, kind: str) -> None:
        self.decisions.append(kind)

    def record_recovery_sample(self, sim_time: float, avg_queue: float) -> None:
        self.recovery_series.append((sim_time, avg_queue))

    def finalize(
        self,
        ev_departure: dict[str, float],
        ev_arrival: dict[str, float],
        recovery_time: float | None,
        total_decisions: int,
        adaptive_actions: int,
    ) -> None:
        if self._ev_departure is not None and config.EV_VEHICLE_ID not in ev_departure:
            ev_departure[config.EV_VEHICLE_ID] = self._ev_departure

        evtt_vals = [
            evtt.compute_evtt(ev_departure[v], ev_arrival.get(v, ev_departure[v]))
            for v in ev_departure
        ]
        evtt_mean = sum(evtt_vals) / len(evtt_vals) if evtt_vals else 0.0
        evsf_val = evsf.compute_evsf(list(self.ev_stops.values()))
        gwsr_val = gwsr.compute_gwsr(self.gwsr_green, self.gwsr_total)
        cvdi_val = cvdi.compute_cvdi(self.civilian_waits[-500:] if self.civilian_waits else [])
        tre_val = tre.compute_tre(recovery_time)
        icp_mean = (
            sum(r["icp"] for r in self.timeseries) / len(self.timeseries)
            if self.timeseries else 0.0
        )
        sas_val = sas.compute_sas(adaptive_actions, total_decisions)

        self._summary = {
            "controller": config.ACTIVE_CONTROLLER,
            "controller_type": config.ACTIVE_CONTROLLER,
            "traffic_profile": config.TRAFFIC_PROFILE,
            "grid": config.GRID_NAME,
            "EVTT": evtt_mean,
            "EVSF": evsf_val,
            "GWSR": gwsr_val,
            "CVDI": cvdi_val,
            "TRE": tre_val,
            "ICP": icp_mean,
            "SAS": sas_val,
            "total_reward": self._cumulative_reward,
            "evtt_per_vehicle": evtt_vals,
            "recovery_time_s": recovery_time,
        }

    def summary(self) -> dict[str, Any]:
        return {
            **self._summary,
            "timeseries": self.timeseries,
            "recovery_series": self.recovery_series,
        }

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.timeseries)

    def load_stream_dataframe(self) -> pd.DataFrame:
        path = Path(self._stream_path)
        if path.exists() and path.stat().st_size > 0:
            return pd.read_csv(path)
        return pd.DataFrame()

    def save_csv(self) -> None:
        config.ensure_dirs()
        summary_path = config.RESULTS_DIR / "metrics_summary.csv"
        row = {k: v for k, v in self._summary.items() if k != "evtt_per_vehicle"}
        pd.DataFrame([row]).to_csv(summary_path, index=False)
        self.to_dataframe().to_csv(config.RESULTS_DIR / "metrics_timeseries.csv", index=False)
