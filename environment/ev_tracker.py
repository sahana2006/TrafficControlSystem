"""
Continuous EV position/speed/junction debug logging.
"""
from __future__ import annotations

from typing import Any

import traci

import config
from environment.traci_utils import next_tls


class EVTracker:
    def __init__(self, logger: Any, interval_s: float | None = None) -> None:
        self.logger = logger
        self.interval_s = interval_s if interval_s is not None else config.EV_LOG_INTERVAL_S
        self._last_log_t = -999.0
        self._depart_time: float | None = None

    def log_continuous(
        self,
        sim_time: float,
        preempted_tls: set[str],
        force: bool = False,
    ) -> dict[str, Any] | None:
        ev_id = config.EV_VEHICLE_ID
        if ev_id not in traci.vehicle.getIDList():
            return None

        if not force and sim_time - self._last_log_t < self.interval_s:
            return None
        self._last_log_t = sim_time

        if self._depart_time is None:
            self._depart_time = sim_time
            self.logger.info(f"[EV] Spawned {ev_id} at t={sim_time:.1f}s")

        pos = traci.vehicle.getPosition(ev_id)
        speed = traci.vehicle.getSpeed(ev_id)
        edge = traci.vehicle.getRoadID(ev_id)
        lane = traci.vehicle.getLaneID(ev_id)

        junction = "—"
        info = next_tls(ev_id)
        if info:
            junction = info[0]

        preempt = "YES" if junction in preempted_tls else "no"
        if preempted_tls:
            preempt = f"YES ({','.join(sorted(preempted_tls))})" if junction in preempted_tls else f"active@{','.join(sorted(preempted_tls))}"

        self.logger.info(f"[EV] Position: ({pos[0]:.1f}, {pos[1]:.1f})")
        self.logger.info(f"[EV] Speed: {speed * 3.6:.1f} km/h ({speed:.2f} m/s)")
        self.logger.info(f"[EV] Current Edge: {edge}")
        self.logger.info(f"[EV] Current Lane: {lane}")
        self.logger.info(f"[EV] Current Junction: J-{junction}")
        self.logger.info(f"[EV] Preemption Active: {preempt}")

        return {
            "vehicle_id": ev_id,
            "position": pos,
            "speed": speed,
            "edge": edge,
            "lane": lane,
            "junction": junction,
            "preemption": junction in preempted_tls,
        }
