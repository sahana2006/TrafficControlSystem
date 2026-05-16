"""
DQN traffic signal controller.
Actions: Hold, Switch, Extend, Preempt on EV-nearest TLS (fallback: max queue).
"""
from __future__ import annotations

from typing import Any

import numpy as np
import traci

import config
from controllers.dqn.dqn_agent import DQNAgent
from controllers.dqn.reward import compute_reward
from controllers.dqn.trainer import DQNTrainer
from environment.action_handler import ActionHandler, SignalAction
from environment.rl_state import encode_state, get_tls_ids, state_dim
from environment.state_extractor import StateExtractor
from environment.traci_utils import next_tls


class DQNController:
    ACTION_MAP = (
        SignalAction.HOLD,
        SignalAction.SWITCH,
        SignalAction.EXTEND,
        SignalAction.PREEMPT,
    )

    def __init__(
        self,
        action_handler: ActionHandler,
        state_extractor: StateExtractor,
        metrics_collector: Any,
        live_logger: Any = None,
        train: bool = True,
    ) -> None:
        self.actions = action_handler
        self.state_extractor = state_extractor
        self.metrics = metrics_collector
        self._logger = live_logger
        self.train_mode = train
        self.tls_ids: list[str] = []
        self.agent = DQNAgent(state_dim())
        self.trainer = DQNTrainer(self.agent)
        self.trainer.load_checkpoint()

        self._prev_state: np.ndarray | None = None
        self._prev_action: int | None = None
        self._ev_departure: dict[str, float] = {}
        self._ev_arrival: dict[str, float] = {}
        self._last_ev_stopped = False
        self._total_reward = 0.0
        self._step_rewards: list[float] = []
        self.total_decisions = 0
        self.adaptive_actions = 0
        self._active_preempt: set[str] = set()

    def reset(self) -> None:
        self.tls_ids = get_tls_ids()
        self._prev_state = None
        self._prev_action = None
        self._ev_departure.clear()
        self._ev_arrival.clear()
        self._last_ev_stopped = False
        self._total_reward = 0.0
        self._step_rewards.clear()
        self.total_decisions = 0
        self.adaptive_actions = 0
        self._active_preempt.clear()
        self.metrics.reset()
        if self._logger:
            self._logger.info("DQN controller reset")

    def _focus_tls(self, state: dict[str, Any]) -> str:
        ev_id = config.EV_VEHICLE_ID
        if ev_id in traci.vehicle.getIDList():
            info = next_tls(ev_id)
            if info:
                return info[0]
        intersections = state.get("intersections", {})
        if not intersections:
            return self.tls_ids[0] if self.tls_ids else ""
        return max(intersections.keys(), key=lambda t: intersections[t].queue_length)

    def _phase_for_preempt(self, tls_id: str) -> int:
        try:
            program = traci.trafficlight.getCompleteRedYellowGreenDefinition(tls_id)
            for phase_idx, phase_def in enumerate(program):
                st = phase_def.state if hasattr(phase_def, "state") else str(phase_def)
                if "G" in st:
                    return phase_idx
        except traci.TraCIException:
            pass
        return traci.trafficlight.getPhase(tls_id)

    def _apply_action(self, tls_id: str, action_idx: int) -> None:
        if not tls_id:
            return
        action = self.ACTION_MAP[action_idx]
        if action == SignalAction.PREEMPT:
            self.actions.apply(tls_id, action, self._phase_for_preempt(tls_id))
        else:
            self.actions.apply(tls_id, action)

    def _gwsr_hit(self, state: dict[str, Any]) -> bool:
        ev_id = config.EV_VEHICLE_ID
        if ev_id not in traci.vehicle.getIDList():
            return False
        info = next_tls(ev_id)
        if not info:
            return False
        return "G" in info[2] or "g" in info[2]

    def _ev_stop_event(self, state: dict[str, Any]) -> bool:
        evs = state.get("evs", [])
        if not evs:
            return False
        stopped = evs[0].stopped
        event = stopped and not self._last_ev_stopped
        self._last_ev_stopped = stopped
        return event

    def step(self, state: dict[str, Any]) -> None:
        sim_time = state["time"]
        curr_vec = encode_state(state, self.tls_ids)

        if self._prev_state is not None and self._prev_action is not None:
            reward = compute_reward(
                state,
                ev_stop_event=self._ev_stop_event(state),
                gwsr_hit=self._gwsr_hit(state),
            )
            self._total_reward += reward
            self._step_rewards.append(reward)
            if self.metrics:
                self.metrics.record_reward(reward)
            if self.train_mode:
                done = sim_time >= config.SIMULATION_END_S - 1
                self.trainer.on_transition(
                    self._prev_state,
                    self._prev_action,
                    reward,
                    curr_vec,
                    done,
                )

        action_idx = self.agent.select_action(curr_vec, training=self.train_mode)
        tls_id = self._focus_tls(state)
        self._apply_action(tls_id, action_idx)
        if action_idx == 3:
            self._active_preempt.add(tls_id)
        elif tls_id in self._active_preempt and action_idx != 0:
            self._active_preempt.discard(tls_id)

        self.total_decisions += 1
        self.adaptive_actions += 1
        if self.metrics:
            self.metrics.record_decision(DQNAgent.ACTIONS[action_idx])

        for ev in state.get("evs", []):
            if ev.vehicle_id not in self._ev_departure:
                self._ev_departure[ev.vehicle_id] = sim_time
            route = traci.vehicle.getRoute(ev.vehicle_id) if ev.vehicle_id in traci.vehicle.getIDList() else []
            if route and ev.route_index >= len(route) - 1 and ev.speed < 0.5:
                self._ev_arrival[ev.vehicle_id] = sim_time

        if self._logger and self._prev_action is not None:
            self._logger.info(
                f"[DQN] action={DQNAgent.ACTIONS[action_idx]} tls=J-{tls_id} "
                f"reward={self._step_rewards[-1] if self._step_rewards else 0:.3f}"
            )

        self._prev_state = curr_vec
        self._prev_action = action_idx

    def on_simulation_end(self) -> dict[str, Any]:
        if self.train_mode:
            self.agent.end_episode()
            self.trainer.save_checkpoint()
        self.metrics.finalize(
            ev_departure=self._ev_departure,
            ev_arrival=self._ev_arrival,
            recovery_time=None,
            total_decisions=self.total_decisions,
            adaptive_actions=self.adaptive_actions,
        )
        summary = self.metrics.summary()
        summary["dqn_total_reward"] = self._total_reward
        summary["dqn_episode_rewards"] = self.trainer.reward_history()
        summary["dqn_train_losses"] = self.trainer.loss_history()
        summary["dqn_epsilon"] = self.agent.epsilon
        return summary

    @property
    def sas(self) -> float:
        if self.total_decisions == 0:
            return 0.0
        return self.adaptive_actions / self.total_decisions

    @property
    def preemption(self):
        """Compat shim for env live logger."""
        class _P:
            pass
        p = _P()
        p.active = {t: True for t in self._active_preempt}
        return p
