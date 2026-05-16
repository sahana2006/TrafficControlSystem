"""DQN training utilities and episode management."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import config
from controllers.dqn.dqn_agent import DQNAgent


class DQNTrainer:
    def __init__(self, agent: DQNAgent) -> None:
        self.agent = agent
        self.losses: list[float] = []

    def on_transition(
        self,
        state,
        action: int,
        reward: float,
        next_state,
        done: bool,
    ) -> None:
        self.agent.store(state, action, reward, next_state, done)
        loss = self.agent.train_step()
        if loss is not None:
            self.losses.append(loss)

    def save_checkpoint(self, path: Path | None = None) -> None:
        path = path or config.DQN_MODEL_PATH
        self.agent.save(path)

    def load_checkpoint(self, path: Path | None = None) -> bool:
        path = path or config.DQN_MODEL_PATH
        return self.agent.load(path)

    def reward_history(self) -> list[float]:
        return list(self.agent.episode_rewards)

    def loss_history(self) -> list[float]:
        return list(self.losses)

    def summary(self) -> dict[str, Any]:
        rh = self.reward_history()
        return {
            "train_steps": self.agent.train_steps,
            "epsilon": self.agent.epsilon,
            "episodes": len(rh),
            "mean_episode_reward": sum(rh) / len(rh) if rh else 0.0,
            "total_reward": sum(rh),
        }
