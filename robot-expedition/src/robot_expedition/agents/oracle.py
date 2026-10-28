"""Controlador de referencia que sigue el gradiente BFS hacia el objetivo actual.

No aprende: lee el mapa del simulador. Sirve para pruebas, episodios de ejemplo y
como cota de lo que debería lograr un agente entrenado.
"""

from __future__ import annotations

import gymnasium as gym

from robot_expedition.envs.robot_expedition_env import RobotExpeditionEnv
from robot_expedition.envs.world import DIRECTIONS


class OracleAgent:
    def __init__(self, env: gym.Env):
        self.env: RobotExpeditionEnv = env.unwrapped  # type: ignore[assignment]

    def act(self, observation=None) -> int:
        e = self.env
        x, y = e.pos
        dist = e.world.distances[e.target]
        here = dist[y, x]
        if here <= 0:
            return e.STAY
        # Prefiere seguir de frente si eso también acorta la ruta.
        order = [e.orientation, (e.orientation + 1) % 4, (e.orientation - 1) % 4, (e.orientation + 2) % 4]
        for o in order:
            dx, dy = DIRECTIONS[o]
            nx, ny = x + dx, y + dy
            if e.world.is_free(nx, ny) and dist[ny, nx] == here - 1:
                if o == e.orientation:
                    return e.FORWARD
                return e.TURN_LEFT if o == (e.orientation - 1) % 4 else e.TURN_RIGHT
        return e.STAY
