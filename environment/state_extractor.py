"""
Extract simulation state for controllers and RL agents.

Network model:
  G = (I, R)
  rho_i = N_i / L_i
  Q_i(t+1) = Q_i(t) + A_i(t) - D_i(t)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import traci

import config
from environment.traci_utils import next_tls


@dataclass
class IntersectionState:
    tls_id: str
    queue_length: float
    density: float
    incoming_edges: list[str] = field(default_factory=list)


@dataclass
class EVState:
    vehicle_id: str
    position: tuple[float, float]
    speed: float
    edge_id: str
    lane_id: str
    route_index: int
    waiting_time: float
    stopped: bool
    eta_next_tls: float | None = None


class StateExtractor:
    """Pull queues, densities, and EV telemetry from TraCI."""

    def __init__(self, ev_ids: list[str] | None = None) -> None:
        self.ev_ids = ev_ids if ev_ids is not None else [config.EV_VEHICLE_ID]
        self._tls_to_lanes: dict[str, list[str]] = {}

    def register_tls_lanes(self, tls_id: str, lanes: list[str]) -> None:
        self._tls_to_lanes[tls_id] = lanes

    def _lanes_for_tls(self, tls_id: str) -> list[str]:
        if tls_id in self._tls_to_lanes:
            return self._tls_to_lanes[tls_id]
        controlled = traci.trafficlight.getControlledLanes(tls_id)
        self._tls_to_lanes[tls_id] = list(controlled)
        return self._tls_to_lanes[tls_id]

    def queue_length(self, tls_id: str) -> float:
        total = 0.0
        for lane in self._lanes_for_tls(tls_id):
            try:
                total += traci.lane.getLastStepHaltingNumber(lane)
            except traci.TraCIException:
                pass
        return total

    def density(self, tls_id: str) -> float:
        n_vehicles = 0.0
        total_length = 0.0
        for lane in self._lanes_for_tls(tls_id):
            try:
                n_vehicles += traci.lane.getLastStepVehicleNumber(lane)
                total_length += traci.lane.getLength(lane)
            except traci.TraCIException:
                pass
        L_i = max(total_length, config.DEFAULT_LANE_LENGTH_M)
        return n_vehicles / L_i

    def intersection_states(self) -> dict[str, IntersectionState]:
        states: dict[str, IntersectionState] = {}
        for tls_id in traci.trafficlight.getIDList():
            states[tls_id] = IntersectionState(
                tls_id=tls_id,
                queue_length=self.queue_length(tls_id),
                density=self.density(tls_id),
            )
        return states

    def ev_states(self) -> list[EVState]:
        result: list[EVState] = []
        for vid in self.ev_ids:
            if vid not in traci.vehicle.getIDList():
                continue
            pos = traci.vehicle.getPosition(vid)
            speed = traci.vehicle.getSpeed(vid)
            edge = traci.vehicle.getRoadID(vid)
            lane = traci.vehicle.getLaneID(vid)
            route_idx = traci.vehicle.getRouteIndex(vid)
            wait = traci.vehicle.getWaitingTime(vid)
            stopped = traci.vehicle.getSpeed(vid) < 0.1 and wait > 0.5
            eta = self._estimate_eta(vid, speed)
            result.append(
                EVState(
                    vehicle_id=vid,
                    position=(pos[0], pos[1]),
                    speed=speed,
                    edge_id=edge,
                    lane_id=lane,
                    route_index=route_idx,
                    waiting_time=wait,
                    stopped=stopped,
                    eta_next_tls=eta,
                )
            )
        return result

    def _estimate_eta(self, vid: str, speed: float) -> float | None:
        """ETA_i = d_i / v_EV"""
        v = max(speed, 0.5)
        info = next_tls(vid)
        if info:
            _, dist, _ = info
            return dist / v
        return None

    def distance_to_tls(self, ev: EVState, tls_id: str) -> float | None:
        try:
            tls_lane = self._lanes_for_tls(tls_id)
            if not tls_lane:
                return None
            junction_pos = traci.junction.getPosition(tls_id.replace("GS_", "").split("_")[0])
            dx = ev.position[0] - junction_pos[0]
            dy = ev.position[1] - junction_pos[1]
            return (dx * dx + dy * dy) ** 0.5
        except (traci.TraCIException, ValueError):
            pass
        try:
            for lane in tls_lane:
                if ev.lane_id == lane or ev.edge_id in lane:
                    return traci.vehicle.getDrivingDistance(ev.vehicle_id, lane, 0.0)
        except traci.TraCIException:
            pass
        return None

    def full_state(self) -> dict[str, Any]:
        return {
            "time": traci.simulation.getTime(),
            "intersections": self.intersection_states(),
            "evs": self.ev_states(),
            "vehicle_count": traci.vehicle.getIDCount(),
        }

    def average_queue(self) -> float:
        tls_list = traci.trafficlight.getIDList()
        if not tls_list:
            return 0.0
        return sum(self.queue_length(t) for t in tls_list) / len(tls_list)

    def total_queue(self) -> float:
        return sum(self.queue_length(t) for t in traci.trafficlight.getIDList())
