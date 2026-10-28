"""Cinco transiciones manuales. Con ``pytest -s`` imprime la tabla."""

import numpy as np

from robot_expedition.demo import five_transitions, print_table


def test_five_transitions():
    rows = five_transitions(seed=0)
    print_table(rows)

    assert len(rows) == 5
    # La nueva observación de un paso es la observación del siguiente.
    for prev, nxt in zip(rows, rows[1:]):
        for key in prev["next_obs"]:
            np.testing.assert_array_equal(prev["next_obs"][key], nxt["obs"][key])
    # El desglose suma la recompensa total.
    for row in rows:
        assert abs(sum(row["breakdown"].values()) - row["reward"]) < 1e-9
    # El quinto paso choca con la caja coral.
    assert "collision" in rows[4]["events"]
    assert rows[4]["breakdown"]["collision"] < 0
