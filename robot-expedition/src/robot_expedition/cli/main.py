"""Punto de entrada del CLI `robot-exp`."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.live import Live
from rich.table import Table

from robot_expedition import __version__
from robot_expedition.cli.keys import read_key
from robot_expedition.cli.render import CONTROLS, render_view
from robot_expedition.config import DEFAULT_CONFIG_PATH, ConfigError, ExperimentConfig, load_config
from robot_expedition.envs import DiscreteStateWrapper, RobotExpeditionEnv
from robot_expedition.envs.world import TARGETS
from robot_expedition.export.episode import DEFAULT_EPISODES_DIR, EpisodeRecorder, load_episode

app = typer.Typer(help="ROBOT EXPEDITION: CLI del ambiente de RL.", no_args_is_help=True)
console = Console()

KEYMAP = {
    "w": RobotExpeditionEnv.FORWARD,
    "a": RobotExpeditionEnv.TURN_LEFT,
    "d": RobotExpeditionEnv.TURN_RIGHT,
    "s": RobotExpeditionEnv.BACKWARD,
    " ": RobotExpeditionEnv.STAY,
}
QUIT_KEYS = {"q", "\x1b", "\x03"}
INCIDENT_CHOICES = {"none": None, "blocked_corridor": "blocked_corridor"}


@app.callback()
def main() -> None:
    """ROBOT EXPEDITION: CLI del ambiente de RL."""


@app.command()
def version() -> None:
    """Muestra la versión instalada."""
    console.print(f"robot-expedition [bold cyan]{__version__}[/]")


def _load_or_exit(path: Path) -> ExperimentConfig:
    try:
        return load_config(path)
    except ConfigError as err:
        _print_errors(err)
        raise typer.Exit(1)


def _print_errors(err: ConfigError) -> None:
    console.print("[bold red]Configuración inválida[/]")
    for message in err.errors:
        console.print(f"  [red]✗[/] {message}")


def _parse_incident(value: Optional[str], config: ExperimentConfig) -> Optional[str]:
    if value is None:
        return config.incident
    if value not in INCIDENT_CHOICES:
        raise typer.BadParameter(f"usa una de: {', '.join(INCIDENT_CHOICES)}", param_hint="--incident")
    return INCIDENT_CHOICES[value]


@app.command()
def play(
    config: Path = typer.Option(DEFAULT_CONFIG_PATH, "--config", "-c", exists=True, dir_okay=False,
                                help="YAML del experimento."),
    seed: int = typer.Option(0, help="Semilla del ruido de los sensores."),
    incident: Optional[str] = typer.Option(None, help="none | blocked_corridor (por defecto, el del YAML)."),
    keys: Optional[str] = typer.Option(None, help="Juega una secuencia de teclas sin teclado, p. ej. 'wwdww'."),
    out_dir: Path = typer.Option(DEFAULT_EPISODES_DIR, help="Carpeta donde se guarda el episodio."),
    save: bool = typer.Option(True, "--save/--no-save", help="Guardar la partida como episodio JSON."),
    live: bool = typer.Option(False, "--live", help="Enviar los frames al visor three.js (Fase 2)."),
) -> None:
    """Mueve el robot a mano: W avanzar, A/D girar, S retroceder, espacio quedarse, Q salir."""
    cfg = _load_or_exit(config)
    try:
        base = RobotExpeditionEnv(cfg, incident=_parse_incident(incident, cfg))
    except ConfigError as err:
        _print_errors(err)
        raise typer.Exit(1)
    if live:
        console.print("[yellow]--live todavía no está disponible: el visor three.js llega en la Fase 2.[/]")
    if keys is None and not sys.stdin.isatty():
        console.print("[red]play necesita una terminal interactiva. Usa --keys para una secuencia de teclas.[/]")
        raise typer.Exit(2)

    env = EpisodeRecorder(base, out_dir=out_dir, auto_save=False, label="manual",
                          metadata={"agent": "human", "source": "robot-exp play", "seed": seed})
    env.reset(seed=seed)
    map_dict = base.world.to_dict()
    trail = [base.pos]
    state = {"action": None, "quit": False}

    def view():
        return render_view(map_dict, base.export_frame(include_map=False), trail, action=state["action"],
                           footer=CONTROLS, episode_label=cfg.name, quit_early=state["quit"])

    def apply(key: str) -> bool:
        """Aplica una tecla. Devuelve True si la partida terminó."""
        key = key.lower()
        if key in QUIT_KEYS:
            state["quit"] = True
            return True
        if key not in KEYMAP:
            return False
        state["action"] = KEYMAP[key]
        *_, terminated, truncated, _ = env.step(KEYMAP[key])
        if base.pos != trail[-1]:
            trail.append(base.pos)
        return terminated or truncated

    if keys is not None:
        console.print(view())
        for key in keys:
            if key.lower() not in KEYMAP and key.lower() not in QUIT_KEYS:
                continue
            done = apply(key)
            if not state["quit"]:
                console.print(view())
            if done:
                break
    else:
        with Live(view(), console=console, screen=True, auto_refresh=False) as screen:
            done = False
            while not done:
                done = apply(read_key())
                screen.update(view(), refresh=True)
        console.print(view())

    if save and len(env.frames) > 1:
        env.metadata["ended_by"] = "quit" if state["quit"] else "terminated" if base.terminated else \
            "truncated" if base.truncated else "keys_exhausted"
        path = env.save()
        console.print(f"Episodio guardado en [bold]{path}[/] ({len(env.frames)} frames)")


@app.command()
def replay(
    episode: Path = typer.Argument(..., exists=True, dir_okay=False, help="Archivo JSON del episodio."),
    fps: float = typer.Option(4.0, min=0.1, help="Frames por segundo."),
    final_only: bool = typer.Option(False, "--final-only", help="Mostrar solo el último frame."),
) -> None:
    """Reproduce un episodio guardado en la terminal."""
    try:
        data = load_episode(episode)
    except (ValueError, OSError) as err:
        console.print(f"[red]{err}[/]")
        raise typer.Exit(1)
    map_dict, frames = data["map"], data["frames"]
    label = f"{data['experiment']} · {episode.name}"

    trails: list[list[tuple[int, int]]] = []
    trail: list[tuple[int, int]] = []
    for frame in frames:
        pos = (frame["robot"]["x"], frame["robot"]["y"])
        if not trail or trail[-1] != pos:
            trail.append(pos)
        trails.append(list(trail))

    def view(i: int):
        footer = f"frame {i + 1}/{len(frames)} · {fps:g} fps"
        return render_view(map_dict, frames[i], trails[i], action=frames[i].get("action"),
                           title="ROBOT EXPEDITION · replay", footer=footer, episode_label=label)

    if final_only or not sys.stdout.isatty():
        console.print(view(len(frames) - 1))
        return
    with Live(view(0), console=console, auto_refresh=False) as screen:
        for i in range(1, len(frames)):
            time.sleep(1.0 / fps)
            screen.update(view(i), refresh=True)


@app.command("validate-config")
def validate_config(
    path: Path = typer.Argument(..., exists=True, dir_okay=False, help="YAML del experimento."),
) -> None:
    """Valida parámetros, unidades, rangos y el mapa (rutas con BFS)."""
    cfg = _load_or_exit(path)

    table = Table(title=f"Parámetros · {cfg.name}", header_style="bold #8fd3e0")
    for column in ("Sección", "Parámetro", "Valor", "Unidad", "Rango", ""):
        table.add_column(column)
    for row in cfg.param_rows():
        lo, hi = row["range"]
        table.add_row(row["section"], row["name"], str(row["value"]), row["unit"], f"[{lo}, {hi}]", "[green]✓[/]")
    console.print(table)

    incidents: list[Optional[str]] = [None]
    if cfg.map.get("seed") is None and cfg.map.get("blocked_corridor"):
        incidents.append("blocked_corridor")
    ok = True
    for inc in incidents:
        label = inc or "sin incidente"
        try:
            env = RobotExpeditionEnv(cfg, incident=inc)
        except ConfigError as err:
            ok = False
            console.print(f"[bold red]Mapa ({label}) inválido[/]")
            for message in err.errors:
                console.print(f"  [red]✗[/] {message}")
            continue
        w = env.world
        start_leg = w.distance(TARGETS[0], *w.start[:2])
        b1_b2 = w.distance("beacon_2", *w.beacons[0])
        b2_base = w.distance("base", *w.beacons[1])
        console.print(
            f"[green]✓[/] Mapa ({label}): {w.size}×{w.size} m, {len(w.obstacles)} obstáculos · ruta BFS "
            f"base→1 {start_leg} m, 1→2 {b1_b2} m, 2→base {b2_base} m (total {start_leg + b1_b2 + b2_base} m)"
        )
    if not ok:
        raise typer.Exit(1)
    wrapper = DiscreteStateWrapper(RobotExpeditionEnv(cfg, incident=None))
    states, actions = wrapper.q_table_shape
    console.print(f"[green]✓[/] Q-table: {states} estados × {actions} acciones = {states * actions} valores")
    console.print(f"[bold green]Configuración válida:[/] {path}")


if __name__ == "__main__":
    app()
