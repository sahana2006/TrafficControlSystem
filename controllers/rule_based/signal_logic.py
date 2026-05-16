"""
Rule-based baseline traffic signal controller.

IF EV distance < threshold: activate_preemption()
ELIF queue_length > congestion_limit: extend_green()
ELIF EV lane already green: hold_phase()
ELSE: continue normal cycle()
"""
from __future__ import annotations

from typing import Any

import traci

import config
from controllers.rule_based.congestion_control import CongestionController
from controllers.rule_based.preemption import PreemptionManager
from controllers.rule_based.recovery import RecoveryManager
from environment.action_handler import ActionHandler, SignalAction
from environment.state_extractor import StateExtractor


class RuleBasedController:
    """Baseline controller with hooks for future RL replacement."""

    def __init__(
        self,
        action_handler: ActionHandler,
        state_extractor: StateExtractor,
        metrics_collector: Any,
        live_logger: Any = None,
    ) -> None:
        self.actions = action_handler
        self.state_extractor = state_extractor
        self.metrics = metrics_collector
        self._logger = live_logger
        self.preemption = PreemptionManager(action_handler, state_extractor)
        self.congestion = CongestionController(action_handler, state_extractor)
        self.recovery = RecoveryManager(action_handler)
        self.total_decisions = 0
        self.adaptive_actions = 0
        self._ev_departure: dict[str, float] = {}
        self._ev_arrival: dict[str, float] = {}
        self._last_ev_active = False

    def reset(self) -> None:
        self.total_decisions = 0
        self.adaptive_actions = 0
        self.recovery.reset()
        self.preemption.active.clear()
        self.metrics.reset()

    def step(self, state: dict[str, Any]) -> None:
        sim_time = state["time"]
        intersections = state["intersections"]
        evs = state["evs"]

        for ev in evs:
            if ev.vehicle_id not in self._ev_departure:
                self._ev_departure[ev.vehicle_id] = sim_time

            target = self.preemption.detect(ev)
            if target and self.preemption.should_preempt(target):
                self._apply_decision("preempt")
                self.preemption.activate(target)
                self._last_ev_active = True
                if hasattr(self, "_logger") and self._logger:
                    self._logger.info(
                        f"Preemption activated at J-{target.tls_id} "
                        f"(dist={target.distance:.1f}m, phase={target.phase})"
                    )
            else:
                self.preemption.update(ev)

            if self._lane_is_green(ev):
                self._apply_decision("hold")
                from environment.traci_utils import next_tls as get_next_tls
                info = get_next_tls(ev.vehicle_id)
                if info:
                    self.actions.apply(info[0], SignalAction.HOLD)

        if not evs and self._last_ev_active:
            self.recovery.start_recovery(sim_time)
            self._last_ev_active = False
            for vid, dep in list(self._ev_departure.items()):
                if vid not in self._ev_arrival:
                    self._ev_arrival[vid] = sim_time

        congested = self.congestion.congested_intersections(intersections)
        for tls_id in congested:
            if not self.actions.is_preempted(tls_id):
                self._apply_decision("extend")
                self.congestion.extend_green(tls_id)

        if self.recovery._recovery_start is not None:
            avg_q = self.state_extractor.average_queue()
            self.recovery.step(sim_time, avg_q)
            self.metrics.record_recovery_sample(sim_time, avg_q)

        for ev in evs:
            if ev.vehicle_id in traci.vehicle.getIDList():
                route = traci.vehicle.getRoute(ev.vehicle_id)
                if ev.route_index >= len(route) - 1 and ev.speed < 0.5:
                    self._ev_arrival[ev.vehicle_id] = sim_time

        # Normal cycle for non-preempted signals
        for tls_id in traci.trafficlight.getIDList():
            if self.actions.is_preempted(tls_id):
                continue
            if tls_id in congested:
                continue
            remaining = traci.trafficlight.getNextSwitch(tls_id) - sim_time
            if remaining <= 0.5:
                self._apply_decision("switch")
                self.actions.apply(tls_id, SignalAction.SWITCH)

    def _apply_decision(self, kind: str) -> None:
        self.total_decisions += 1
        if kind in ("preempt", "extend", "hold", "switch"):
            self.adaptive_actions += 1
        self.metrics.record_decision(kind)

    def _lane_is_green(self, ev) -> bool:
        from environment.traci_utils import next_tls as get_next_tls
        info = get_next_tls(ev.vehicle_id)
        if info:
            return "G" in info[2] or "g" in info[2]
        return False

    def on_simulation_end(self) -> dict[str, Any]:
        self.metrics.finalize(
            ev_departure=self._ev_departure,
            ev_arrival=self._ev_arrival,
            recovery_time=self.recovery.recovery_time,
            total_decisions=self.total_decisions,
            adaptive_actions=self.adaptive_actions,
        )
        return self.metrics.summary()

    @property
    def sas(self) -> float:
        if self.total_decisions == 0:
            return 0.0
        return self.adaptive_actions / self.total_decisions
