"""DQN agent with epsilon-greedy exploration and target network."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

import config
from controllers.dqn.model import DQNModel
from controllers.dqn.replay_buffer import ReplayBuffer


class DQNAgent:
  ACTIONS = ("hold", "switch", "extend", "preempt")

  def __init__(
      self,
      state_dim: int,
      action_dim: int = 4,
      lr: float | None = None,
      gamma: float | None = None,
  ) -> None:
      self.state_dim = state_dim
      self.action_dim = action_dim
      self.gamma = gamma if gamma is not None else config.DQN_GAMMA
      self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

      self.policy_net = DQNModel(state_dim, action_dim, config.DQN_HIDDEN).to(self.device)
      self.target_net = DQNModel(state_dim, action_dim, config.DQN_HIDDEN).to(self.device)
      self.target_net.load_state_dict(self.policy_net.state_dict())
      self.optimizer = optim.Adam(self.policy_net.parameters(), lr=lr or config.DQN_LR)
      self.buffer = ReplayBuffer(config.DQN_BUFFER_SIZE)
      self.epsilon = config.DQN_EPSILON_START
      self.train_steps = 0
      self.episode_rewards: list[float] = []
      self._episode_return = 0.0

  def select_action(self, state: np.ndarray, training: bool = True) -> int:
      if training and np.random.random() < self.epsilon:
          return int(np.random.randint(self.action_dim))
      with torch.no_grad():
          s = torch.FloatTensor(state).unsqueeze(0).to(self.device)
          q = self.policy_net(s)
          return int(q.argmax(dim=1).item())

  def store(self, state, action, reward, next_state, done) -> None:
      self.buffer.push(state, action, reward, next_state, done)
      self._episode_return += reward

  def train_step(self) -> float | None:
      if len(self.buffer) < config.DQN_BATCH_SIZE:
          return None
      states, actions, rewards, next_states, dones = self.buffer.sample(config.DQN_BATCH_SIZE)
      states_t = torch.FloatTensor(states).to(self.device)
      actions_t = torch.LongTensor(actions).to(self.device)
      rewards_t = torch.FloatTensor(rewards).to(self.device)
      next_states_t = torch.FloatTensor(next_states).to(self.device)
      dones_t = torch.FloatTensor(dones).to(self.device)

      q_values = self.policy_net(states_t).gather(1, actions_t.unsqueeze(1)).squeeze(1)
      with torch.no_grad():
          next_q = self.target_net(next_states_t).max(1)[0]
          target = rewards_t + self.gamma * next_q * (1 - dones_t)

      loss = nn.functional.smooth_l1_loss(q_values, target)
      self.optimizer.zero_grad()
      loss.backward()
      torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), 1.0)
      self.optimizer.step()

      self.train_steps += 1
      if self.train_steps % config.DQN_TARGET_UPDATE == 0:
          self.target_net.load_state_dict(self.policy_net.state_dict())
      self.epsilon = max(
          config.DQN_EPSILON_END,
          self.epsilon * config.DQN_EPSILON_DECAY,
      )
      return float(loss.item())

  def end_episode(self) -> float:
      ret = self._episode_return
      self.episode_rewards.append(ret)
      self._episode_return = 0.0
      return ret

  def save(self, path: Path) -> None:
      path.parent.mkdir(parents=True, exist_ok=True)
      torch.save(
          {
              "policy": self.policy_net.state_dict(),
              "target": self.target_net.state_dict(),
              "epsilon": self.epsilon,
              "episode_rewards": self.episode_rewards,
          },
          path,
      )

  def load(self, path: Path) -> bool:
      if not path.exists():
          return False
      ckpt = torch.load(path, map_location=self.device, weights_only=False)
      self.policy_net.load_state_dict(ckpt["policy"])
      self.target_net.load_state_dict(ckpt.get("target", ckpt["policy"]))
      self.epsilon = ckpt.get("epsilon", config.DQN_EPSILON_END)
      self.episode_rewards = ckpt.get("episode_rewards", [])
      return True
