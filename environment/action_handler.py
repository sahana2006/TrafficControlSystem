"""
TraCI action interface for traffic signal control.
Designed for reuse by rule-based and future RL controllers.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

import traci


class SignalAction(Enum):
    HOLD = "hold"
    SWITCH = "switch"
    EXTEND = "extend"
    PREEMPT = "preempt"


class ActionHandler:
    """Maps high-level controller actions to TraCI traffic-light commands."""

    def __init__(self) -> None:
        self._extended: dict[str, int] = {}
        self._preempted: set[str] = set()

    def apply(self, tls_id: str, action: SignalAction, target_phase: int | None = None) -> None:
        if tls_id not in traci.trafficlight.getIDList():
            return

        current = traci.trafficlight.getPhase(tls_id)
        try:
            n_phases = traci.trafficlight.getPhaseNumber(tls_id)
        except (traci.TraCIException, AttributeError):
            n_phases = 4
        n_phases = max(n_phases, 1)

        if action == SignalAction.HOLD:
            traci.trafficlight.setPhaseDuration(tls_id, 9999)

        elif action == SignalAction.SWITCH:
            next_phase = (current + 1) % n_phases
            traci.trafficlight.setPhase(tls_id, next_phase)

        elif action == SignalAction.EXTEND:
            remaining = traci.trafficlight.getNextSwitch(tls_id) - traci.simulation.getTime()
            traci.trafficlight.setPhaseDuration(tls_id, max(remaining, 0) + 5)

        elif action == SignalAction.PREEMPT:
            if target_phase is not None:
                traci.trafficlight.setPhase(tls_id, target_phase % n_phases)
                traci.trafficlight.setPhaseDuration(tls_id, 9999)
                self._preempted.add(tls_id)

    def release_preemption(self, tls_id: str) -> None:
        if tls_id in self._preempted:
            traci.trafficlight.setPhaseDuration(tls_id, 15)
            self._preempted.discard(tls_id)

    def is_preempted(self, tls_id: str) -> bool:
        return tls_id in self._preempted

    def set_program(self, tls_id: str, program_id: str) -> None:
        traci.trafficlight.setProgram(tls_id, program_id)

    def get_phase_state(self, tls_id: str) -> str:
        return traci.trafficlight.getRedYellowGreenState(tls_id)

    def snapshot(self, tls_id: str) -> dict[str, Any]:
        return {
            "tls_id": tls_id,
            "phase": traci.trafficlight.getPhase(tls_id),
            "state": self.get_phase_state(tls_id),
            "remaining": traci.trafficlight.getNextSwitch(tls_id) - traci.simulation.getTime(),
        }
