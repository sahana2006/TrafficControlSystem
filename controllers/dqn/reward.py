"""
DQN reward:
  + EV speed
  - queue length
  - civilian delay
  - EV stops
  + green wave success
"""
from __future__ import annotations

from typing import Any

import traci

import config


def compute_reward(
    state: dict[str, Any],
    ev_stop_event: bool = False,
    gwsr_hit: bool = False,
) -> float:
    intersections = state.get("intersections", {})
    avg_queue = (
        sum(i.queue_length for i in intersections.values()) / len(intersections)
        if intersections else 0.0
    )

    ev_speed = 0.0
    civilian_delay = 0.0
    ev_id = config.EV_VEHICLE_ID
    if ev_id in traci.vehicle.getIDList():
        ev_speed = traci.vehicle.getSpeed(ev_id)

    delays = []
    for vid in traci.vehicle.getIDList():
        try:
            if traci.vehicle.getTypeID(vid) != config.EV_TYPE_ID:
                delays.append(traci.vehicle.getWaitingTime(vid))
        except traci.TraCIException:
            pass
    if delays:
        civilian_delay = sum(delays) / len(delays)

    r = 0.0
    r += config.DQN_REWARD_EV_SPEED * (ev_speed / max(config.EV_MAX_SPEED_MPS, 1.0))
    r -= config.DQN_REWARD_QUEUE * min(avg_queue / 20.0, 1.0)
    r -= config.DQN_REWARD_DELAY * min(civilian_delay / 100.0, 1.0)
    if ev_stop_event:
        r -= config.DQN_REWARD_EV_STOP
    if gwsr_hit:
        r += config.DQN_REWARD_GWSR
    return float(r)
