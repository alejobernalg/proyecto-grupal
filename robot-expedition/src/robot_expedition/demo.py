"""Cinco transiciones manuales: observación → acción → física → recompensa → nueva observación.

Uso: ``python -m robot_expedition.demo [config.yaml]``
"""

from __future__ import annotations

import sys
from typing import Any

from rich.console import Console
from rich.table import Table

from robot_expedition.envs import RobotExpeditionEnv
from robot_expedition.envs.world import ORIENTATIONS

# avanzar, girar derecha, avanzar, avanzar, avanzar (choca con la caja coral)
DEMO_ACTIONS = (0, 2, 0, 0, 0)


def summarize_obs(obs: dict[str, Any]) -> str:
    rays = " ".join(f"{r:.1f}" for r in obs["rays"])
    fwd, right = obs["target_direction"]
    return (
        f"rayos [{rays}]\n"
        f"obj dir (fr {fwd:+.2f}, der {right:+.2f}) d={obs['target_distance'][0]:.0f} m\n"
        f"ori {ORIENTATIONS[obs['orientation']]}  v={obs['velocity'][0]:+.0f}  giro={obs['turn'][0]:+.0f}\n"
        f"bat {obs['battery'][0]:.3f}  etapa {obs['stage']}"
    )


def five_transitions(config: Any = None, seed: int = 0, actions=DEMO_ACTIONS) -> list[dict[str, Any]]:
    env = RobotExpeditionEnv(config)
    obs, _ = env.reset(seed=seed)
    rows = []
    for t, action in enumerate(actions, start=1):
        pos_before, ori_before, bat_before = env.pos, ORIENTATIONS[env.orientation], env.battery
        new_obs, reward, terminated, truncated, info = env.step(action)
        physics = (
            f"({pos_before[0]},{pos_before[1]}) {ori_before} → "
            f"({env.pos[0]},{env.pos[1]}) {ORIENTATIONS[env.orientation]}\n"
            f"batería {bat_before:.1f} → {env.battery:.1f}"
        )
        if "collision" in info["events"]:
            physics += "\nCOLISIÓN: no se mueve"
        rows.append(
            {
                "t": t,
                "obs": obs,
                "action": action,
                "action_name": env.ACTION_NAMES[action],
                "physics": physics,
                "reward": reward,
                "breakdown": info["reward_breakdown"],
                "next_obs": new_obs,
                "events": info["events"],
                "terminated": terminated,
                "truncated": truncated,
            }
        )
        obs = new_obs
    return rows


def print_table(rows: list[dict[str, Any]], console: Console | None = None) -> None:
    console = console or Console(width=200)
    table = Table(title="ROBOT EXPEDITION · cinco transiciones", show_lines=True)
    table.add_column("t", justify="right")
    table.add_column("Observación s", style="cyan")
    table.add_column("Acción", style="bold")
    table.add_column("Física")
    table.add_column("Recompensa", justify="right")
    table.add_column("Nueva observación s'", style="cyan")
    for row in rows:
        parts = [f"{k} {v:+.3f}" for k, v in row["breakdown"].items() if abs(v) > 1e-12]
        reward = f"[bold]{row['reward']:+.3f}[/]\n" + "\n".join(parts)
        table.add_row(
            str(row["t"]),
            summarize_obs(row["obs"]),
            f"{row['action']} {row['action_name']}",
            row["physics"],
            reward,
            summarize_obs(row["next_obs"]),
        )
    console.print(table)


def main() -> None:
    config = sys.argv[1] if len(sys.argv) > 1 else None
    print_table(five_transitions(config))


if __name__ == "__main__":
    main()
