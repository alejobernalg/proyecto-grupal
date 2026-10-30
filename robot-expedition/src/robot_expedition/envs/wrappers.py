"""Wrappers del ambiente."""

from __future__ import annotations

import gymnasium as gym
from gymnasium import spaces

from robot_expedition.envs.robot_expedition_env import RobotExpeditionEnv


class DiscreteStateWrapper(gym.ObservationWrapper):
    """Convierte el estado en un índice discreto para Q-learning tabular.

    Estado discreto: (x, y, orientación, etapa, nivel de batería), con

        índice = (((x·n + y)·4 + orientación)·3 + etapa)·k + nivel

    donde n es el lado del mapa y k = ``wrapper.battery_levels``. La etapa ya codifica
    qué balizas se visitaron, porque solo se pueden visitar en orden.

    Tamaño de la Q-table = n·n·4·3·k estados × 5 acciones. Para el experimento 1
    (n = 12, k = 4): 12·12·4·3·4 = 6 912 estados × 5 acciones = 34 560 valores Q.
    Incluye celdas ocupadas por obstáculos, que nunca se visitan.

    Ojo: este wrapper usa el estado interno del simulador (posición exacta), no los
    rayos ruidosos de la observación. Es una simplificación deliberada para Q-learning.
    """

    NUM_ORIENTATIONS = 4
    NUM_STAGES = 3

    def __init__(self, env: gym.Env, battery_levels: int | None = None):
        super().__init__(env)
        base: RobotExpeditionEnv = env.unwrapped  # type: ignore[assignment]
        self.size = base.world.size
        self.battery_levels = battery_levels or base.config.wrapper["battery_levels"]
        self.observation_space = spaces.Discrete(self.num_states)

    @property
    def num_states(self) -> int:
        return self.size * self.size * self.NUM_ORIENTATIONS * self.NUM_STAGES * self.battery_levels

    @property
    def q_table_shape(self) -> tuple[int, int]:
        return (self.num_states, int(self.action_space.n))

    def battery_level(self, battery_fraction: float) -> int:
        return min(self.battery_levels - 1, int(battery_fraction * self.battery_levels))

    def encode(self, x: int, y: int, orientation: int, stage: int, level: int) -> int:
        return (((x * self.size + y) * self.NUM_ORIENTATIONS + orientation) * self.NUM_STAGES + stage) \
            * self.battery_levels + level

    def decode(self, index: int) -> tuple[int, int, int, int, int]:
        index, level = divmod(index, self.battery_levels)
        index, stage = divmod(index, self.NUM_STAGES)
        index, orientation = divmod(index, self.NUM_ORIENTATIONS)
        x, y = divmod(index, self.size)
        return x, y, orientation, stage, level

    def observation(self, observation) -> int:
        base: RobotExpeditionEnv = self.env.unwrapped  # type: ignore[assignment]
        x, y = base.pos
        level = self.battery_level(base.battery / base.battery_capacity)
        return self.encode(x, y, base.orientation, base.stage, level)
