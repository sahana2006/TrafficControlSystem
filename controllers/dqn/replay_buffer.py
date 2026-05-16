"""Experience replay buffer for DQN."""
from __future__ import annotations

from collections import deque
from typing import Deque, Tuple

import numpy as np


class ReplayBuffer:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.buffer: Deque[Tuple[np.ndarray, int, float, np.ndarray, bool]] = deque(maxlen=capacity)

    def push(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ) -> None:
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size: int) -> Tuple[np.ndarray, ...]:
        idx = np.random.choice(len(self.buffer), batch_size, replace=False)
        batch = [self.buffer[i] for i in idx]
        states = np.stack([b[0] for b in batch])
        actions = np.array([b[1] for b in batch], dtype=np.int64)
        rewards = np.array([b[2] for b in batch], dtype=np.float32)
        next_states = np.stack([b[3] for b in batch])
        dones = np.array([b[4] for b in batch], dtype=np.float32)
        return states, actions, rewards, next_states, dones

    def __len__(self) -> int:
        return len(self.buffer)
