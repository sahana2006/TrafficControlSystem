"""
Live console + file logging for EV traffic control simulation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import traci

import config
from environment.traci_utils import next_tls


class LiveLogger:
    def __init__(self, log_path: Path | None = None, interval_s: float = 5.0) -> None:
        self.log_path = log_path or (config.RESULTS_DIR / "logs.txt")
        self.interval_s = interval_s
        self._last_log_t = -999.0
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("", encoding="utf-8")

    def info(self, msg: str) -> None:
        line = f"[INFO] {msg}"
        print(line, flush=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def log_step(
        self,
        sim_time: float,
        evs: list[Any],
        intersections: dict,
        preempted_tls: set[str],
    ) -> None:
        if sim_time - self._last_log_t < self.interval_s:
            return
        self._last_log_t = sim_time

        avg_q = (
            sum(ist.queue_length for ist in intersections.values()) / len(intersections)
            if intersections else 0.0
        )
        icp = sum(ist.queue_length for ist in intersections.values()) / max(
            config.DEFAULT_LANE_LENGTH_M * max(len(intersections), 1), 1
        )

        self.info(f"t={sim_time:.0f}s | avg queue={avg_q:.1f} | congestion(ICP)={icp:.4f}")

        for ev in evs:
            jid = self._junction_label(ev)
            spd = ev.speed * 3.6
            self.info(
                f"EV {ev.vehicle_id} @ ({ev.position[0]:.0f},{ev.position[1]:.0f}) "
                f"speed={spd:.1f} km/h edge={ev.edge_id}"
            )
            info = next_tls(ev.vehicle_id)
            if info:
                tls_id, dist, state = info
                phase = traci.trafficlight.getPhase(tls_id)
                preempt = "ACTIVE" if tls_id in preempted_tls else "idle"
                self.info(
                    f"EV approaching {tls_id} (J-{tls_id}) dist={dist:.1f}m "
                    f"phase={phase} signal={state[:12]}... preemption={preempt}"
                )
                if tls_id in preempted_tls:
                    self.info(f"Preemption active at J-{tls_id}")

        for tls_id in preempted_tls:
            if not evs:
                q = intersections.get(tls_id)
                qlen = q.queue_length if q else 0
                phase = traci.trafficlight.getPhase(tls_id)
                self.info(f"Preemption holding at J-{tls_id} phase={phase} queue={qlen:.0f}")

    def _junction_label(self, ev) -> str:
        info = next_tls(ev.vehicle_id)
        return info[0] if info else ev.edge_id
