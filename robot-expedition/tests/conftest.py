import pytest

from robot_expedition.agents.oracle import OracleAgent
from robot_expedition.config import DEFAULT_CONFIG_PATH, load_config
from robot_expedition.envs import RobotExpeditionEnv


@pytest.fixture
def config():
    return load_config(DEFAULT_CONFIG_PATH)


@pytest.fixture
def env(config):
    env = RobotExpeditionEnv(config)
    env.reset(seed=0)
    return env


def run_oracle(env: RobotExpeditionEnv, max_steps: int = 1000):
    """Corre el oracle hasta terminar. Devuelve la lista de (reward, info)."""
    agent = OracleAgent(env)
    history = []
    for _ in range(max_steps):
        _, reward, terminated, truncated, info = env.step(agent.act())
        history.append((reward, info))
        if terminated or truncated:
            break
    return history
