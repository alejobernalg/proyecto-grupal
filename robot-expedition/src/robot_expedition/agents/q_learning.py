"""Q-learning tabular sobre ``DiscreteStateWrapper`` con ε-greedy decreciente."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np

from robot_expedition.envs import DiscreteStateWrapper, RobotExpeditionEnv

MODEL_FORMAT = "robot-expedition/q-table@1"


@dataclass
class EpisodeStats:
    episode: int
    reward: float
    steps: int
    success: bool
    collisions: int
    battery: float
    epsilon: float


@dataclass
class TrainingHistory:
    episodes: list[EpisodeStats] = field(default_factory=list)

    def window(self, n: int = 100) -> list[EpisodeStats]:
        return self.episodes[-n:]

    def mean_reward(self, n: int = 100) -> float:
        w = self.window(n)
        return float(np.mean([e.reward for e in w])) if w else 0.0

    def success_rate(self, n: int = 100) -> float:
        w = self.window(n)
        return float(np.mean([e.success for e in w])) if w else 0.0

    def mean_steps(self, n: int = 100) -> float:
        w = self.window(n)
        return float(np.mean([e.steps for e in w])) if w else 0.0


class QLearningAgent:
    def __init__(self, num_states: int, num_actions: int, alpha: float, gamma: float, seed: int = 0):
        self.q = np.zeros((num_states, num_actions), dtype=np.float64)
        self.alpha = alpha
        self.gamma = gamma
        self.rng = np.random.default_rng(seed)

    def greedy(self, state: int) -> int:
        row = self.q[state]
        best = np.flatnonzero(row == row.max())
        return int(best[0] if len(best) == 1 else self.rng.choice(best))

    def act(self, state: int, epsilon: float = 0.0) -> int:
        if self.rng.random() < epsilon:
            return int(self.rng.integers(self.q.shape[1]))
        return self.greedy(state)

    def update(self, state: int, action: int, reward: float, next_state: int, terminated: bool) -> None:
        # Solo un estado terminal corta el bootstrap; un truncamiento por max_steps no.
        target = reward if terminated else reward + self.gamma * self.q[next_state].max()
        self.q[state, action] += self.alpha * (target - self.q[state, action])

    # ------------------------------------------------------------------ persistencia
    def save(self, path: str | Path, metadata: dict[str, Any]) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        meta = {"format": MODEL_FORMAT, "alpha": self.alpha, "gamma": self.gamma, **metadata}
        with path.open("wb") as fh:  # con un archivo abierto numpy no añade otra extensión
            np.savez_compressed(fh, q=self.q, metadata=np.array(json.dumps(meta, ensure_ascii=False)))
        return path

    @classmethod
    def load(cls, path: str | Path) -> tuple[QLearningAgent, dict[str, Any]]:
        with np.load(Path(path), allow_pickle=False) as data:
            meta = json.loads(str(data["metadata"]))
            if meta.get("format") != MODEL_FORMAT:
                raise ValueError(f"{path} no es un modelo {MODEL_FORMAT}")
            q = data["q"]
        agent = cls(q.shape[0], q.shape[1], meta["alpha"], meta["gamma"])
        agent.q = q.astype(np.float64)
        return agent, meta


def epsilon_at(episode: int, total: int, start: float, end: float, decay_fraction: float) -> float:
    """ε lineal de ``start`` a ``end`` durante ``decay_fraction`` de los episodios; luego fijo."""
    decay_episodes = max(1, int(total * decay_fraction))
    progress = min(1.0, episode / decay_episodes)
    return start + (end - start) * progress


def make_env(config: Any, incident: Any = None) -> DiscreteStateWrapper:
    kwargs = {} if incident is None else {"incident": incident}
    return DiscreteStateWrapper(RobotExpeditionEnv(config, **kwargs))


def default_checkpoints(total: int) -> list[int]:
    """Episodios donde se guarda el modelo para ver cómo aprende: 0, 1 %, 5 %, 15 %, 35 % y 100 %."""
    return sorted({0, *(max(1, round(total * f)) for f in (0.01, 0.05, 0.15, 0.35)), total})


def train(env: DiscreteStateWrapper, callback: Callable[[EpisodeStats, TrainingHistory], None] | None = None,
          episodes: int | None = None, checkpoints: Iterable[int] = (),
          on_checkpoint: Callable[[int, QLearningAgent], None] | None = None) -> tuple[QLearningAgent, TrainingHistory]:
    """Entrena. ``on_checkpoint(k, agent)`` se llama tras ``k`` episodios para cada k de ``checkpoints``."""
    base: RobotExpeditionEnv = env.unwrapped  # type: ignore[assignment]
    hp = base.config.agent
    total = episodes or hp["episodes"]
    agent = QLearningAgent(env.observation_space.n, env.action_space.n, hp["alpha"], hp["gamma"], hp["seed"])
    history = TrainingHistory()
    pending = set(checkpoints)
    if on_checkpoint and 0 in pending:
        on_checkpoint(0, agent)

    for ep in range(total):
        epsilon = epsilon_at(ep, total, hp["epsilon_start"], hp["epsilon_end"], hp["epsilon_decay_fraction"])
        state, _ = env.reset(seed=hp["seed"] + ep)
        reward_sum = 0.0
        while True:
            action = agent.act(state, epsilon)
            next_state, reward, terminated, truncated, info = env.step(action)
            agent.update(state, action, reward, next_state, terminated)
            reward_sum += reward
            state = next_state
            if terminated or truncated:
                break
        stats = EpisodeStats(ep + 1, reward_sum, info["step"], info["success"], info["collisions"],
                             info["battery"], epsilon)
        history.episodes.append(stats)
        if callback:
            callback(stats, history)
        if on_checkpoint and ep + 1 in pending:
            on_checkpoint(ep + 1, agent)
    return agent, history


def run_greedy(agent: QLearningAgent, env: Any, seed: int = 0) -> dict[str, Any]:
    """Corre un episodio con la política greedy. ``env`` puede llevar EpisodeRecorder encima del wrapper."""
    state, _ = env.reset(seed=seed)
    reward_sum = 0.0
    while True:
        state, reward, terminated, truncated, info = env.step(agent.greedy(state))
        reward_sum += reward
        if terminated or truncated:
            break
    base: RobotExpeditionEnv = env.unwrapped
    return {
        "success": info["success"],
        "reward": reward_sum,
        "steps": info["step"],
        "visited": info["visited"],
        "battery": info["battery"],
        "battery_fraction": info["battery"] / base.battery_capacity,
        "path_length": info["path_length"],
        "collisions": info["collisions"],
        "terminated": terminated,
        "truncated": truncated,
    }
