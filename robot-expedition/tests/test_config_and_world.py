import copy

import pytest
import yaml

from robot_expedition.config import DEFAULT_CONFIG_PATH, ConfigError, load_config
from robot_expedition.envs import RobotExpeditionEnv
from robot_expedition.envs.world import generate_random_world


@pytest.fixture
def raw():
    return yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))


def test_default_config_loads(config):
    assert config.name == "experimento_1"
    assert config.env["map_size"] == 12
    assert config.incident is None
    assert len(config.param_rows()) == 27
    assert config.mission == "full"


def test_value_out_of_range_is_rejected(raw):
    raw["env"]["map_size"]["value"] = 50
    with pytest.raises(ConfigError, match="map_size: valor 50"):
        load_config(raw)


def test_range_outside_simulator_limits_is_rejected(raw):
    raw["env"]["max_speed"]["range"] = [1, 10]
    with pytest.raises(ConfigError, match="límites del simulador"):
        load_config(raw)


def test_wrong_unit_and_missing_param_are_reported_together(raw):
    raw["env"]["sensor_range"]["unit"] = "cm"
    del raw["reward"]["beacon_bonus"]
    with pytest.raises(ConfigError) as err:
        load_config(raw)
    assert len(err.value.errors) == 2


def test_int_param_rejects_float(raw):
    raw["env"]["max_steps"]["value"] = 10.5
    with pytest.raises(ConfigError, match="entero"):
        load_config(raw)


def test_map_without_route_is_rejected(raw):
    # Un muro que cruza toda la sala separa la base de las balizas.
    raw["map"]["obstacles"] = [{"x": 0, "y": 6, "w": 12, "h": 1}]
    with pytest.raises(ConfigError, match="no hay ruta"):
        RobotExpeditionEnv(load_config(raw))


def test_narrow_corridor_is_rejected(raw):
    raw["map"]["obstacles"].append({"x": 9, "y": 3, "w": 1, "h": 1})  # a 1 m de la caja gris
    with pytest.raises(ConfigError, match="separados 1 m"):
        RobotExpeditionEnv(load_config(raw))


def test_beacon_inside_obstacle_is_rejected(raw):
    raw["map"]["beacons"][0] = {"id": 1, "x": 6, "y": 1}
    with pytest.raises(ConfigError, match="dentro de un obstáculo"):
        RobotExpeditionEnv(load_config(raw))


def test_unknown_incident_is_rejected(raw):
    raw["incident"] = "earthquake"
    with pytest.raises(ConfigError, match="incident"):
        load_config(raw)


@pytest.mark.parametrize("seed", range(10))
def test_random_maps_are_valid_and_reproducible(seed):
    a = generate_random_world(14, 2, 6, seed)
    b = generate_random_world(14, 2, 6, seed)
    assert a.to_dict() == b.to_dict()


def test_seed_in_yaml_builds_random_map(raw):
    raw["map"]["seed"] = 3
    env = RobotExpeditionEnv(load_config(copy.deepcopy(raw)))
    assert env.world.seed == 3
    assert env.world.to_dict() != RobotExpeditionEnv(load_config(DEFAULT_CONFIG_PATH)).world.to_dict()
