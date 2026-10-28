import numpy as np
import pytest
from typer.testing import CliRunner

from robot_expedition.agents.oracle import OracleAgent
from robot_expedition.agents.q_learning import (
    QLearningAgent,
    default_checkpoints,
    epsilon_at,
    make_env,
    run_greedy,
    train,
)
from robot_expedition.cli.main import app
from robot_expedition.config import PROJECT_ROOT, load_config
from robot_expedition.envs import RobotExpeditionEnv

A_TO_B = PROJECT_ROOT / "configs" / "a_to_b.yaml"


def test_a_to_b_config_extends_experiment_1():
    cfg = load_config(A_TO_B)
    assert cfg.name == "a_to_b" and cfg.mission == "a_to_b"
    assert cfg.agent["episodes"] == 3000
    assert cfg.env["map_size"] == 12  # heredado


def test_a_to_b_mission_ends_at_beacon_1():
    env = RobotExpeditionEnv(A_TO_B)
    env.reset(seed=0)
    agent = OracleAgent(env)
    total, info = 0.0, {}
    while True:
        _, reward, terminated, truncated, info = env.step(agent.act())
        total += reward
        if terminated or truncated:
            break
    assert info["success"] and info["visited"] == [1]
    assert "mission_complete" in info["events"]
    assert info["reward_breakdown"]["return"] == env.rewards["return_bonus"]
    assert info["reward_breakdown"]["progress"] > 0  # sin salto del potencial al terminar


def test_epsilon_schedule():
    assert epsilon_at(0, 100, 1.0, 0.1, 0.5) == 1.0
    assert epsilon_at(25, 100, 1.0, 0.1, 0.5) == pytest.approx(0.55)
    assert epsilon_at(80, 100, 1.0, 0.1, 0.5) == pytest.approx(0.1)


def test_default_checkpoints():
    assert default_checkpoints(3000) == [0, 30, 150, 450, 1050, 3000]


def test_q_update_uses_bootstrap_unless_terminal():
    agent = QLearningAgent(2, 2, alpha=0.5, gamma=0.9)
    agent.q[1] = [2.0, 4.0]
    agent.update(0, 0, 1.0, 1, terminated=False)
    assert agent.q[0, 0] == 0.5 * (1.0 + 0.9 * 4.0)
    agent.update(0, 1, 1.0, 1, terminated=True)
    assert agent.q[0, 1] == 0.5


def test_training_learns_to_reach_b():
    env = make_env(A_TO_B)
    agent, history = train(env, episodes=1500)
    assert history.success_rate() > 0.9
    assert run_greedy(agent, env)["success"]


def test_save_and_load_roundtrip(tmp_path):
    agent = QLearningAgent(4, 5, 0.1, 0.95)
    agent.q = np.arange(20, dtype=float).reshape(4, 5)
    path = agent.save(tmp_path / "m.npz", {"trained_episodes": 7})
    loaded, meta = QLearningAgent.load(path)
    np.testing.assert_array_equal(loaded.q, agent.q)
    assert meta["trained_episodes"] == 7 and loaded.gamma == 0.95


def test_cli_train_watch_evaluate(tmp_path):
    runner = CliRunner()
    models = tmp_path / "models"
    result = runner.invoke(app, ["train", "--config", str(A_TO_B), "--episodes", "40", "--models-dir", str(models),
                                 "--runs-dir", str(tmp_path / "runs"), "--no-export"])
    assert result.exit_code == 0, result.output
    assert (models / "a_to_b.npz").exists() and (models / "a_to_b_ep00000.npz").exists()
    run_dir = next((tmp_path / "runs").iterdir())
    for name in ("config.yaml", "run.json", "metrics.csv"):
        assert (run_dir / name).exists()
    assert len(list((run_dir / "episodes").glob("*.json"))) == len(default_checkpoints(40))

    result = runner.invoke(app, ["watch", "--model", str(models / "a_to_b.npz"), "--final-only", "--no-save"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["evaluate", "--model", str(models / "a_to_b.npz"), "--seeds", "2"])
    assert result.exit_code == 0, result.output
    assert "sin incidente" in result.output and "blocked_corridor" in result.output
