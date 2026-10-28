import json

from robot_expedition.agents.oracle import OracleAgent
from robot_expedition.envs import DiscreteStateWrapper, RobotExpeditionEnv
from robot_expedition.export.episode import EpisodeRecorder, load_episode


def test_q_table_size_for_experiment_1(config):
    wrapped = DiscreteStateWrapper(RobotExpeditionEnv(config))
    assert wrapped.num_states == 12 * 12 * 4 * 3 * 4 == 6912
    assert wrapped.q_table_shape == (6912, 5)


def test_encode_decode_roundtrip(config):
    wrapped = DiscreteStateWrapper(RobotExpeditionEnv(config))
    for index in (0, 1, 777, wrapped.num_states - 1):
        assert wrapped.encode(*wrapped.decode(index)) == index


def test_wrapper_observation_tracks_state(config):
    wrapped = DiscreteStateWrapper(RobotExpeditionEnv(config))
    obs, _ = wrapped.reset(seed=0)
    assert wrapped.observation_space.contains(obs)
    assert wrapped.decode(obs) == (1, 10, 0, 0, 3)
    obs, *_ = wrapped.step(0)
    assert wrapped.decode(obs)[:2] == (1, 9)


def test_recorder_saves_episode(config, tmp_path):
    env = EpisodeRecorder(RobotExpeditionEnv(config), out_dir=tmp_path, label="oracle")
    env.reset(seed=0)
    agent = OracleAgent(env)
    steps = 0
    while True:
        steps += 1
        *_, terminated, truncated, _ = env.step(agent.act())
        if terminated or truncated:
            break
    assert env.saved_path is not None and env.saved_path.parent == tmp_path
    episode = load_episode(env.saved_path)
    assert len(episode["frames"]) == steps + 1
    assert episode["map"]["size"] == 12
    assert episode["frames"][-1]["success"] is True
    assert "map" not in episode["frames"][0]
    json.dumps(episode)
