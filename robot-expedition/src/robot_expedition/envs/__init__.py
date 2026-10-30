"""Ambiente ROBOT EXPEDITION y sus wrappers. Importar este paquete registra el ambiente."""

from gymnasium.envs.registration import register, registry

from robot_expedition.envs.robot_expedition_env import RobotExpeditionEnv
from robot_expedition.envs.wrappers import DiscreteStateWrapper

ENV_ID = "RobotExpedition-v0"

if ENV_ID not in registry:
    # El ambiente trunca por sí mismo con max_steps del YAML, así que no se añade TimeLimit.
    register(id=ENV_ID, entry_point="robot_expedition.envs.robot_expedition_env:RobotExpeditionEnv")

__all__ = ["ENV_ID", "DiscreteStateWrapper", "RobotExpeditionEnv"]
