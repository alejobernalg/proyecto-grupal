"""Vista de terminal con Rich.

Solo dibuja el mapa y los frames que exporta el simulador (``World.to_dict()`` y
``export_frame()``). No contiene reglas de juego: física ≠ decoración.
"""

from __future__ import annotations

from typing import Any, Iterable

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

FLOOR = "#c9a46a"
WALL = "#d4d4d4"
OBSTACLE_COLORS = {"orange": "#e07b2a", "coral": "#e5574b", "gray": "#8a8f98"}
BLOCKED = "#7a1f1f"
BASE = "#2e9e4f"
BEACON = "#19c3d8"
BEACON_VISITED = "#3ccf6e"
ARROWS = {"N": "▲", "E": "▶", "S": "▼", "O": "◀"}

ACTION_LABELS = ("avanzar", "girar izq.", "girar der.", "retroceder", "quedarse")
TARGET_LABELS = {"beacon_1": "Baliza 1", "beacon_2": "Baliza 2", "base": "Base"}
STAGE_LABELS = ("0 · ir a baliza 1", "1 · ir a baliza 2", "2 · volver a la base")
REWARD_LABELS = {
    "progress": "progreso",
    "beacon": "baliza",
    "return": "retorno",
    "time": "tiempo",
    "battery": "batería",
    "collision": "colisión",
    "depletion": "batería agotada",
}
EVENT_LABELS = {
    "collision": "¡choque!",
    "battery_depleted": "batería agotada",
    "mission_complete": "misión completada",
    "beacon_1": "baliza 1 visitada",
    "beacon_2": "baliza 2 visitada",
    "beacon_1_revisit": "baliza 1 ya visitada (0 pts)",
    "beacon_2_revisit": "baliza 2 ya visitada (0 pts)",
    "beacon_1_out_of_order": "baliza 1 fuera de orden (0 pts)",
    "beacon_2_out_of_order": "baliza 2 fuera de orden (0 pts)",
}
CONTROLS = "W avanzar · A/D girar · S retroceder · espacio quedarse · Q salir"


def _rect_contains(rect: dict[str, int], x: int, y: int) -> bool:
    return rect["x"] <= x < rect["x"] + rect["w"] and rect["y"] <= y < rect["y"] + rect["h"]


def render_grid(map_dict: dict[str, Any], frame: dict[str, Any], trail: Iterable[tuple[int, int]] = ()) -> Text:
    size = map_dict["size"]
    robot = frame["robot"]
    beacons = {(b["x"], b["y"]): b for b in frame["beacons"]}
    trail_cells = set(trail)
    ray_hits = {(int(r["end"][0]), int(r["end"][1])) for r in frame.get("rays", []) if r["hit"]}

    text = Text()
    wall_row = Text("  " * (size + 2), style=f"on {WALL}")
    text.append_text(wall_row)
    text.append("\n")
    for y in range(size):
        text.append("  ", style=f"on {WALL}")
        for x in range(size):
            text.append_text(_cell(map_dict, x, y, robot, beacons, trail_cells, ray_hits))
        text.append("  ", style=f"on {WALL}")
        text.append("\n")
    text.append_text(wall_row)
    return text


def _cell(map_dict, x, y, robot, beacons, trail_cells, ray_hits) -> Text:
    if (x, y) == (robot["x"], robot["y"]):
        bg = BASE if _rect_contains(map_dict["base"], x, y) else FLOOR
        return Text(ARROWS[robot["orientation"]] + " ", style=f"bold #ffffff on {bg}")
    if (x, y) in beacons:
        b = beacons[(x, y)]
        color = BEACON_VISITED if b["visited"] else BEACON
        return Text(f"{b['id']} ", style=f"bold #0b1d2a on {color}")
    for rect in map_dict.get("blocked", []):
        if _rect_contains(rect, x, y):
            return Text("XX", style=f"bold #ffb4b4 on {BLOCKED}")
    for rect in map_dict["obstacles"]:
        if _rect_contains(rect, x, y):
            return Text("  ", style=f"on {OBSTACLE_COLORS.get(rect['kind'], OBSTACLE_COLORS['gray'])}")
    if _rect_contains(map_dict["base"], x, y):
        return Text("B ", style=f"bold #e8ffe8 on {BASE}")
    if (x, y) in ray_hits:
        return Text("• ", style=f"bold #0e7c8c on {FLOOR}")
    if (x, y) in trail_cells:
        return Text("· ", style=f"bold #ffffff on {FLOOR}")
    return Text("  ", style=f"on {FLOOR}")


def battery_bar(fraction: float, width: int = 20) -> Text:
    color = "green" if fraction > 0.5 else "yellow" if fraction > 0.25 else "red"
    filled = round(fraction * width)
    bar = Text("█" * filled, style=color)
    bar.append("░" * (width - filled), style="grey37")
    bar.append(f" {fraction * 100:5.1f}%", style=f"bold {color}")
    return bar


def outcome_message(frame: dict[str, Any], quit_early: bool = False) -> tuple[str, str] | None:
    """(mensaje, estilo) del final del episodio, o None si sigue en curso."""
    if frame["success"]:
        if frame["collisions"] == 0:
            return "Misión completada sin colisiones", "bold green"
        return f"Misión completada con {frame['collisions']} colisiones", "bold green"
    if frame["terminated"]:
        return "Batería agotada", "bold red"
    if frame["truncated"]:
        return "Tiempo agotado (max_steps)", "bold yellow"
    if quit_early:
        return "Partida abandonada", "bold yellow"
    return None


def render_side(frame: dict[str, Any], action: int | None = None, episode_label: str | None = None) -> Table:
    side = Table.grid(padding=(0, 1))
    side.add_column(style="bold #8fd3e0", no_wrap=True)
    side.add_column(no_wrap=True)
    if episode_label:
        side.add_row("Episodio", episode_label)
    side.add_row("Paso", str(frame["step"]))
    battery = frame["battery"]
    side.add_row("Batería", battery_bar(battery["fraction"]))
    side.add_row("", f"{battery['value']:.1f} / {battery['capacity']:.0f} u")
    side.add_row("Objetivo", TARGET_LABELS[frame["target"]] if not frame["success"] else "—")
    side.add_row("Etapa", STAGE_LABELS[frame["stage"]])
    visited = ", ".join(str(v) for v in frame["visited"]) or "ninguna"
    side.add_row("Balizas", visited)
    side.add_row("Colisiones", str(frame["collisions"]))
    side.add_row("Recorrido", f"{frame['path_length']} m")
    if action is not None:
        side.add_row("Acción", ACTION_LABELS[action])
    side.add_row("", "")

    reward = frame["reward"]
    style = "green" if reward["step"] > 0 else "red" if reward["step"] < 0 else "white"
    side.add_row("Recompensa", Text(f"{reward['step']:+.3f}", style=f"bold {style}") + Text(" este paso"))
    for key, value in reward["breakdown"].items():
        if abs(value) > 1e-9:
            side.add_row("", Text(f"  {REWARD_LABELS.get(key, key):<16}{value:+.3f}", style="grey70"))
    side.add_row("Total", Text(f"{reward['total']:+.3f}", style="bold"))

    events = [EVENT_LABELS.get(e, e) for e in frame["events"]]
    if events:
        side.add_row("Eventos", Text(" · ".join(events), style="bold magenta"))
    return side


def render_view(map_dict: dict[str, Any], frame: dict[str, Any], trail: Iterable[tuple[int, int]] = (),
                action: int | None = None, title: str = "ROBOT EXPEDITION", footer: str | None = None,
                episode_label: str | None = None, quit_early: bool = False) -> Panel:
    layout = Table.grid(padding=(0, 3))
    layout.add_row(render_grid(map_dict, frame, trail), render_side(frame, action, episode_label))
    parts: list[Any] = [layout]
    outcome = outcome_message(frame, quit_early)
    if outcome:
        message, style = outcome
        parts.append(Text(f"\n{message}", style=style, justify="center"))
    return Panel(Group(*parts), title=f"[bold]{title}[/]", subtitle=footer, border_style="#2b4a63", expand=False)
