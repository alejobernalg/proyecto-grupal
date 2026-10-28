"""Las balizas solo cuentan en orden: 1 y luego 2."""

from conftest import run_oracle

BEACON_2 = (10, 9)


def test_beacon_2_before_beacon_1_gives_no_bonus(env):
    env.reset(seed=0, options={"position": (10, 8), "orientation": "S"})
    _, reward, _, _, info = env.step(env.FORWARD)
    assert env.pos == BEACON_2
    assert info["reward_breakdown"]["beacon"] == 0
    assert "beacon_2_out_of_order" in info["events"]
    assert env.visited == [] and env.stage == 0 and env.target == "beacon_1"


def test_beacon_2_counts_after_beacon_1(env):
    # Pasa primero por la baliza 2 (no cuenta) y luego hace la misión completa.
    env.reset(seed=0, options={"position": (10, 8), "orientation": "S"})
    env.step(env.FORWARD)
    history = run_oracle(env)
    assert env.success and env.visited == [1, 2]
    bonuses = [(i["events"], i["reward_breakdown"]["beacon"]) for _, i in history if i["reward_breakdown"]["beacon"]]
    assert [events for events, _ in bonuses] == [["beacon_1"], ["beacon_2"]]


def test_returning_to_base_without_beacons_is_not_success(env):
    env.reset(seed=0, options={"position": (3, 10), "orientation": "O"})
    _, _, terminated, _, info = env.step(env.FORWARD)
    assert env.world.base.contains(*env.pos)
    assert not terminated and not info["success"]
    assert info["reward_breakdown"]["return"] == 0
