import gymnasium as gym
import numpy as np
import pytest
from gymnasium.utils.env_checker import check_env

from robot_expedition.envs import ENV_ID, RobotExpeditionEnv
from conftest import run_oracle


def test_check_env_passes(env):
    check_env(env, skip_render_check=True)


def test_registered_with_gym_make():
    env = gym.make(ENV_ID)
    obs, info = env.reset(seed=1)
    assert env.observation_space.contains(obs)
    assert info["target"] == "beacon_1"


def test_initial_state(env):
    assert env.pos == (1, 10)
    assert env.orientation == 0
    assert env.battery == env.battery_capacity
    assert env.stage == 0 and env.visited == [] and env.collisions == 0


def test_collision_does_not_move(env):
    env.reset(options={"position": (3, 9), "orientation": "E"})  # al este está la caja coral
    _, reward, *_, info = env.step(env.FORWARD)
    assert env.pos == (3, 9)
    assert env.collisions == 1
    assert "collision" in info["events"]
    assert info["reward_breakdown"]["collision"] == -env.rewards["collision_penalty"]


def test_wall_is_collision(env):
    env.reset(options={"position": (11, 0), "orientation": "N"})
    env.step(env.FORWARD)
    assert env.pos == (11, 0) and env.collisions == 1


def test_battery_cost_per_action(env):
    costs = env.config.env
    expected = {
        env.FORWARD: costs["battery_cost_forward"],
        env.TURN_LEFT: costs["battery_cost_turn"],
        env.TURN_RIGHT: costs["battery_cost_turn"],
        env.BACKWARD: costs["battery_cost_backward"],
        env.STAY: costs["battery_cost_stay"],
    }
    for action, cost in expected.items():
        env.reset(options={"position": (5, 5), "orientation": "N"})
        env.step(action)
        assert env.battery == pytest.approx(env.battery_capacity - cost)
    assert costs["battery_cost_forward"] > costs["battery_cost_turn"] > costs["battery_cost_stay"]


def test_turns_and_backward(env):
    env.reset(options={"position": (5, 5), "orientation": "N"})
    env.step(env.TURN_RIGHT)
    assert env.orientation == 1
    env.step(env.TURN_LEFT)
    env.step(env.TURN_LEFT)
    assert env.orientation == 3
    env.step(env.BACKWARD)  # mirando al oeste, retrocede hacia el este
    assert env.pos == (6, 5) and env.orientation == 3


def test_oracle_completes_mission(env):
    history = run_oracle(env)
    _, info = history[-1]
    assert info["success"] and env.terminated and not env.truncated
    assert info["visited"] == [1, 2]
    beacons = [i["reward_breakdown"]["beacon"] for _, i in history if i["reward_breakdown"]["beacon"]]
    assert beacons == [env.rewards["beacon_bonus"]] * 2
    assert history[-1][1]["reward_breakdown"]["return"] == env.rewards["return_bonus"]
    assert env.collisions == 0


def test_battery_depletion_terminates(config):
    config.env["battery_capacity"] = 2.0
    env = RobotExpeditionEnv(config)
    env.reset(seed=0)
    _, _, terminated, _, info = env.step(env.FORWARD)
    assert not terminated
    _, reward, terminated, truncated, info = env.step(env.FORWARD)
    assert terminated and not truncated and not info["success"]
    assert "battery_depleted" in info["events"]
    assert info["reward_breakdown"]["depletion"] == -env.rewards["depletion_penalty"]


def test_truncation_at_max_steps(config):
    config.env["max_steps"] = 5
    env = RobotExpeditionEnv(config)
    env.reset(seed=0)
    for _ in range(4):
        assert not env.step(env.STAY)[3]
    _, _, terminated, truncated, _ = env.step(env.STAY)
    assert truncated and not terminated


def test_rays_shorten_near_obstacles(config):
    config.env["distance_noise_std"] = 0.0
    env = RobotExpeditionEnv(config)
    obs, _ = env.reset(options={"position": (3, 9), "orientation": "E"})
    center = obs["rays"][4]
    assert center == pytest.approx(0.5, abs=0.05)  # caja coral pegada al frente
    obs, _ = env.reset(options={"position": (5, 4), "orientation": "S"})
    assert obs["rays"][4] > 1.0


def test_ray_noise_is_seeded(env):
    a, _ = env.reset(seed=42)
    b, _ = env.reset(seed=42)
    np.testing.assert_array_equal(a["rays"], b["rays"])


def test_incident_blocks_corridor_and_forces_detour(config):
    normal = RobotExpeditionEnv(config, incident=None)
    normal.reset(seed=0)
    blocked = RobotExpeditionEnv(config, incident="blocked_corridor")
    blocked.reset(seed=0)
    assert normal.world.is_free(10, 6) and not blocked.world.is_free(10, 6)
    run_oracle(normal)
    run_oracle(blocked)
    assert normal.success and blocked.success
    assert blocked.path_length > normal.path_length


def test_export_frame_is_json_serializable(env):
    import json

    env.step(env.FORWARD)
    frame = env.export_frame()
    text = json.dumps(frame)
    for key in ("map", "robot", "rays", "beacons", "battery", "reward", "stage", "step"):
        assert key in frame
    assert len(frame["rays"]) == 9
    assert json.loads(text)["robot"]["orientation"] == "N"
