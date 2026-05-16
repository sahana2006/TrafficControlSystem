"""
Fixed-size RL state encoding (scalable via MAX_TLS padding).
"""
from __future__ import annotations

from typing import Any

import numpy as np
import traci

import config
from environment.traci_utils import next_tls


def get_tls_ids() -> list[str]:
    return sorted(traci.trafficlight.getIDList())


def encode_state(state: dict[str, Any], tls_ids: list[str] | None = None) -> np.ndarray:
    """
    Vector: per-TLS [queue_norm, density_norm, phase_norm] * MAX_TLS
            + [ev_speed_norm, ev_dist_norm, ev_stopped, gwsr_flag, avg_queue_norm]
    """
    tls_ids = tls_ids or get_tls_ids()
    max_tls = config.DQN_MAX_TLS
    intersections = state.get("intersections", {})
    vec: list[float] = []

    for i in range(max_tls):
        if i < len(tls_ids):
            tls_id = tls_ids[i]
            ist = intersections.get(tls_id)
            if ist:
                q = min(ist.queue_length / 20.0, 1.0)
                d = min(ist.density * 10.0, 1.0)
                try:
                    phase = traci.trafficlight.getPhase(tls_id)
                    try:
                        n = len(traci.trafficlight.getCompleteRedYellowGreenDefinition(tls_id))
                    except traci.TraCIException:
                        n = 4
                    p = phase / max(n, 1)
                except traci.TraCIException:
                    p = 0.0
                vec.extend([q, d, p])
            else:
                vec.extend([0.0, 0.0, 0.0])
        else:
            vec.extend([0.0, 0.0, 0.0])

    ev_speed = 0.0
    ev_dist = 1.0
    ev_stopped = 0.0
    gwsr_flag = 0.0
    ev_id = config.EV_VEHICLE_ID
    if ev_id in traci.vehicle.getIDList():
        ev_speed = min(traci.vehicle.getSpeed(ev_id) / config.EV_MAX_SPEED_MPS, 1.0)
        info = next_tls(ev_id)
        if info:
            ev_dist = min(info[1] / config.EV_DETECTION_RADIUS_M, 1.0)
            if "G" in info[2] or "g" in info[2]:
                gwsr_flag = 1.0
        if traci.vehicle.getSpeed(ev_id) < 0.1:
            ev_stopped = 1.0

    avg_q = 0.0
    if intersections:
        avg_q = sum(i.queue_length for i in intersections.values()) / len(intersections)
    avg_q = min(avg_q / 20.0, 1.0)

    vec.extend([ev_speed, ev_dist, ev_stopped, gwsr_flag, avg_q])
    return np.array(vec, dtype=np.float32)


def state_dim() -> int:
    return config.DQN_MAX_TLS * 3 + 5
