"""
Traffic recovery after EV exit:
- normalize signal timings
- reduce queue imbalance
- restore standard phase cycles
TRE = 1 / T_recovery
"""
from __future__ import annotations

import time

import traci

import config
from environment.action_handler import ActionHandler


class RecoveryManager:
    def __init__(self, action_handler: ActionHandler) -> None:
        self.actions = action_handler
        self._recovery_start: float | None = None
        self._recovery_duration: float | None = None
        self._baseline_queues: list[float] = []

    def start_recovery(self, sim_time: float) -> None:
        if self._recovery_start is None:
            self._recovery_start = sim_time

    def step(self, sim_time: float, avg_queue: float) -> bool:
        """Returns True when recovery complete."""
        if self._recovery_start is None:
            return True

        elapsed = sim_time - self._recovery_start
        self._baseline_queues.append(avg_queue)

        for tls_id in traci.trafficlight.getIDList():
            if self.actions.is_preempted(tls_id):
                continue
            traci.trafficlight.setPhaseDuration(
                tls_id, min(config.MAX_GREEN_S, config.MIN_GREEN_S + elapsed * 0.1)
            )

        if elapsed >= config.RECOVERY_NORMALIZE_STEPS:
            if len(self._baseline_queues) >= 2:
                recent = self._baseline_queues[-5:]
                if max(recent) - min(recent) < 2.0:
                    self._recovery_duration = elapsed
                    self._recovery_start = None
                    return True
            if elapsed > config.RECOVERY_NORMALIZE_STEPS * 2:
                self._recovery_duration = elapsed
                self._recovery_start = None
                return True
        return False

    @property
    def recovery_time(self) -> float | None:
        return self._recovery_duration

    def tre_score(self) -> float:
        if self._recovery_duration and self._recovery_duration > 0:
            return 1.0 / self._recovery_duration
        return 0.0

    def reset(self) -> None:
        self._recovery_start = None
        self._recovery_duration = None
        self._baseline_queues.clear()
