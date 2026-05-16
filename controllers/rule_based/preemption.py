"""
EV signal preemption workflow:
1. Detect EV within detection radius
2. Identify EV direction
3. Switch signal to EV direction
4. Hold green until EV crosses
5. Restore normal cycle
"""
from __future__ import annotations

from dataclasses import dataclass

import traci

import config
from environment.traci_utils import next_tls
from environment.action_handler import ActionHandler, SignalAction
from environment.state_extractor import EVState, StateExtractor


@dataclass
class PreemptionTarget:
    tls_id: str
    phase: int
    distance: float


class PreemptionManager:
    def __init__(self, action_handler: ActionHandler, state_extractor: StateExtractor) -> None:
        self.actions = action_handler
        self.state = state_extractor
        self.active: dict[str, PreemptionTarget] = {}
        self.cleared_tls: set[str] = set()

    def detect(self, ev: EVState) -> PreemptionTarget | None:
        best: PreemptionTarget | None = None
        for tls_id in traci.trafficlight.getIDList():
            dist = self._distance_to_intersection(ev, tls_id)
            if dist is None or dist > config.EV_DETECTION_RADIUS_M:
                continue
            phase = self._phase_for_ev_lane(ev, tls_id)
            if phase is None:
                continue
            if best is None or dist < best.distance:
                best = PreemptionTarget(tls_id=tls_id, phase=phase, distance=dist)
        return best

    def should_preempt(self, target: PreemptionTarget) -> bool:
        return target.distance < config.EV_PREEMPTION_THRESHOLD_M

    def activate(self, target: PreemptionTarget) -> None:
        self.actions.apply(target.tls_id, SignalAction.PREEMPT, target.phase)
        self.active[target.tls_id] = target
        self.cleared_tls.discard(target.tls_id)

    def update(self, ev: EVState) -> list[str]:
        """Hold preemption until EV clears intersection."""
        released: list[str] = []
        for tls_id, target in list(self.active.items()):
            dist = self._distance_to_intersection(ev, tls_id)
            if dist is not None and dist < config.EV_CLEARANCE_DISTANCE_M:
                continue
            if self._ev_passed_tls(ev, tls_id):
                self.actions.release_preemption(tls_id)
                self.cleared_tls.add(tls_id)
                released.append(tls_id)
                del self.active[tls_id]
        return released

    def _ev_passed_tls(self, ev: EVState, tls_id: str) -> bool:
        info = next_tls(ev.vehicle_id)
        if info:
            nid, dist, _ = info
            if nid != tls_id and dist > config.EV_CLEARANCE_DISTANCE_M:
                return True
        controlled = traci.trafficlight.getControlledLanes(tls_id)
        if ev.lane_id not in controlled and ev.edge_id not in "".join(controlled):
            info2 = next_tls(ev.vehicle_id)
            return info2 is None or info2[0] != tls_id
        return False

    def _distance_to_intersection(self, ev: EVState, tls_id: str) -> float | None:
        info = next_tls(ev.vehicle_id)
        if info and info[0] == tls_id:
            return info[1]
        return None

    def _phase_for_ev_lane(self, ev: EVState, tls_id: str) -> int:
        info = next_tls(ev.vehicle_id)
        if info and info[0] == tls_id and ("G" in info[2] or "g" in info[2]):
            return traci.trafficlight.getPhase(tls_id)
        try:
            program = traci.trafficlight.getCompleteRedYellowGreenDefinition(tls_id)
            for phase_idx, phase_def in enumerate(program):
                state = phase_def.state if hasattr(phase_def, "state") else str(phase_def)
                if "G" in state:
                    return phase_idx
        except traci.TraCIException:
            pass
        return traci.trafficlight.getPhase(tls_id)
