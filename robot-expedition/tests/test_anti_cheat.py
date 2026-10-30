"""Reto del equipo: ¿puede ganar visitando la misma baliza repetidamente?"""

import pytest

from robot_expedition.config import ConfigError
from robot_expedition.envs import RobotExpeditionEnv
from conftest import run_oracle

BEACON_1 = (10, 1)


@pytest.fixture
def long_env(config):
    """Batería y pasos de sobra para que 200 pasos no terminen el episodio."""
    config.env["battery_capacity"] = 500.0
    config.env["max_steps"] = 1000
    return RobotExpeditionEnv(config)


def test_entering_and_leaving_beacon_1_for_200_steps_gives_no_positive_reward(long_env):
    env = long_env
    # Empieza al sur de la baliza 1 mirando al norte y alterna avanzar / retroceder.
    env.reset(seed=0, options={"position": (10, 2), "orientation": "N"})
    rewards, beacon_bonuses, visits = [], 0, 0
    for t in range(200):
        action = env.FORWARD if t % 2 == 0 else env.BACKWARD
        _, reward, terminated, truncated, info = env.step(action)
        rewards.append(reward)
        visits += env.pos == BEACON_1
        beacon_bonuses += info["reward_breakdown"]["beacon"] > 0
        assert not (terminated or truncated)

    assert visits == 100
    assert beacon_bonuses == 1  # solo la primera visita paga
    # Todo lo que viene después de la primera visita (99 entradas y salidas) suma negativo.
    assert sum(rewards[1:]) < 0
    # Y el total no supera al bono de una sola visita legítima.
    assert sum(rewards) < env.rewards["beacon_bonus"]


def test_hovering_next_to_target_without_entering_is_negative(long_env):
    env = long_env
    env.reset(seed=0, options={"position": (10, 3), "orientation": "N"})
    total = 0.0
    for t in range(200):  # (10, 3) ↔ (10, 2), nunca entra a la baliza
        _, reward, terminated, truncated, _ = env.step(env.FORWARD if t % 2 == 0 else env.BACKWARD)
        assert not (terminated or truncated)
        total += reward
    assert env.visited == []
    assert total < 0


@pytest.mark.parametrize("action", ["STAY", "TURN_LEFT", "TURN_RIGHT"])
def test_idling_or_spinning_is_negative(env, action):
    total = sum(env.step(getattr(env, action))[1] for _ in range(100))
    assert total < 0


def test_progress_shaping_telescopes(env):
    """Ir y volver por el mismo camino suma cero en el término de progreso."""
    env.reset(seed=0, options={"position": (5, 4), "orientation": "E"})
    progress = 0.0
    for action in [env.FORWARD] * 3 + [env.BACKWARD] * 3:
        progress += env.step(action)[4]["reward_breakdown"]["progress"]
    assert progress == pytest.approx(0.0)


def test_farming_config_is_rejected(config):
    config.reward["shaping_gamma"] = 0.9  # con γ < 1 quedarse quieto lejos del objetivo pagaría
    with pytest.raises(ConfigError, match="farmear"):
        RobotExpeditionEnv(config)


def test_oracle_cannot_be_beaten_by_revisits(env):
    """Una misión completa gana más que cualquier bucle sobre la baliza 1."""
    history = run_oracle(env)
    assert env.success
    assert sum(r for r, _ in history) > 2 * env.rewards["beacon_bonus"]
