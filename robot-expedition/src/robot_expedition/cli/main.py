"""Punto de entrada del CLI `robot-exp`."""

from __future__ import annotations

import shutil
import sys
import time
import webbrowser
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.live import Live
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeRemainingColumn
from rich.table import Table

from robot_expedition import __version__
from robot_expedition.cli.keys import read_key
from robot_expedition.cli.render import CONTROLS, render_view
from robot_expedition.config import DEFAULT_CONFIG_PATH, PROJECT_ROOT, ConfigError, ExperimentConfig, load_config
from robot_expedition.envs import DiscreteStateWrapper, RobotExpeditionEnv
from robot_expedition.envs.world import TARGETS
from robot_expedition.export.episode import DEFAULT_EPISODES_DIR, EpisodeRecorder, load_episode
from robot_expedition.export.live import DEFAULT_PORT as DEFAULT_LIVE_PORT
from robot_expedition.export.live import LiveServer
from robot_expedition.agents.q_learning import QLearningAgent, default_checkpoints, make_env, run_greedy, train
from robot_expedition.runs import RUNS_DIR, create_run_dir, git_info, write_metrics_csv, write_run_summary

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
    live: bool = typer.Option(False, "--live", help="Enviar cada frame al visor three.js en tiempo real."),
    live_port: int = typer.Option(DEFAULT_LIVE_PORT, help="Puerto WebSocket del modo --live."),
    viewer_url: str = typer.Option("http://localhost:5173", help="URL del visor (npm run dev en viewer/)."),
    open_viewer: bool = typer.Option(True, "--open/--no-open", help="Abrir el visor en el navegador con --live."),
    delay: float = typer.Option(0.0, min=0.0, help="Pausa en segundos entre teclas de --keys (útil con --live)."),
) -> None:
    """Mueve el robot a mano: W avanzar, A/D girar, S retroceder, espacio quedarse, Q salir."""
    cfg = _load_or_exit(config)
    try:
        base = RobotExpeditionEnv(cfg, incident=_parse_incident(incident, cfg))
    except ConfigError as err:
        _print_errors(err)
        raise typer.Exit(1)
    if keys is None and not sys.stdin.isatty():
        console.print("[red]play necesita una terminal interactiva. Usa --keys para una secuencia de teclas.[/]")
        raise typer.Exit(2)

    env = EpisodeRecorder(base, out_dir=out_dir, auto_save=False, label="manual",
                          metadata={"agent": "human", "source": "robot-exp play", "seed": seed})
    env.reset(seed=seed)

    server = _start_live(env.to_dict, live_port, viewer_url, open_viewer) if live else None
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
        if server is not None:
            server.send_frame(env.frames[-1])
        if base.pos != trail[-1]:
            trail.append(base.pos)
        return terminated or truncated

    if keys is not None:
        if server is not None and delay > 0:
            time.sleep(max(delay, 1.0))  # da tiempo a que el visor se conecte
        console.print(view())
        for key in keys:
            if key.lower() not in KEYMAP and key.lower() not in QUIT_KEYS:
                continue
            done = apply(key)
            if not state["quit"]:
                console.print(view())
            if done:
                break
            if delay:
                time.sleep(delay)
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
    if server is not None:
        server.close()


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
    _animate(data, f"{data['experiment']} · {episode.name}", "ROBOT EXPEDITION · replay", fps, final_only)


def _start_live(snapshot, port: int, viewer_url: str, open_viewer: bool) -> LiveServer:
    try:
        server = LiveServer(snapshot, port=port)
    except OSError as err:
        console.print(f"[red]No se pudo abrir el puerto {port} para --live: {err}[/]")
        raise typer.Exit(1)
    url = f"{viewer_url.rstrip('/')}/?live={server.url}"
    console.print(f"[cyan]En vivo:[/] {server.url} · visor: [bold]{url}[/]")
    if open_viewer:
        webbrowser.open(url)
    return server


def _animate(data: dict, label: str, title: str, fps: float, final_only: bool = False,
             live: Optional[dict] = None) -> None:
    """Anima en la terminal los frames de un episodio ya calculado. Con ``live`` (port, viewer_url,
    open_viewer) también los envía al visor al mismo ritmo."""
    map_dict, frames = data["map"], data["frames"]
    shown = [1]
    server = None
    if live is not None:
        server = _start_live(lambda: {**data, "frames": frames[:shown[0]]}, **live)
        time.sleep(1.5)  # da tiempo a que el visor se conecte
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
                           title=title, footer=footer, episode_label=label)

    if server is not None:
        server.send_episode()
    animate_terminal = not final_only and sys.stdout.isatty()
    if not animate_terminal and server is None:
        console.print(view(len(frames) - 1))
        return
    screen = Live(view(0), console=console, auto_refresh=False) if animate_terminal else None
    if screen:
        screen.start()
    try:
        for i in range(1, len(frames)):
            time.sleep(1.0 / fps)
            shown[0] = i + 1
            if server is not None:
                server.send_frame(frames[i])
            if screen:
                screen.update(view(i), refresh=True)
    finally:
        if screen:
            screen.stop()
        if server is not None:
            server.close()
    if not animate_terminal:
        console.print(view(len(frames) - 1))


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


# ---------------------------------------------------------------------------------- Q-learning
MODELS_DIR = PROJECT_ROOT / "models"


def _result_table(title: str, rows: list[dict], first_column: str) -> Table:
    table = Table(title=title, header_style="bold #8fd3e0")
    for column in (first_column, "Misión", "Balizas", "Pasos", "Recorrido", "Colisiones", "Batería", "Recompensa"):
        table.add_column(column, justify="right")
    for row in rows:
        table.add_row(
            str(row["label"]),
            "[green]completa[/]" if row["success"] else "[red]no[/]",
            ", ".join(map(str, row["visited"])) or "—",
            str(row["steps"]),
            f"{row['path_length']} m",
            str(row["collisions"]),
            f"{row['battery_fraction'] * 100:.0f} %",
            f"{row['reward']:+.1f}",
        )
    return table


@app.command("train")
def train_command(
    config: Path = typer.Option(DEFAULT_CONFIG_PATH, "--config", "-c", exists=True, dir_okay=False,
                                help="YAML del experimento."),
    episodes: Optional[int] = typer.Option(None, min=1, help="Sobrescribe agent.episodes del YAML."),
    models_dir: Path = typer.Option(MODELS_DIR, help="Carpeta de las Q-tables."),
    runs_dir: Path = typer.Option(RUNS_DIR, help="Carpeta de las corridas (config, commit, métricas)."),
    export: bool = typer.Option(True, "--export/--no-export",
                                help="Copiar los episodios de cada checkpoint a data/episodes para el visor."),
) -> None:
    """Entrena Q-learning tabular y guarda checkpoints para ver cómo aprende."""
    cfg = _load_or_exit(config)
    if episodes is not None:
        cfg.agent["episodes"] = episodes
    try:
        env = make_env(cfg)
    except ConfigError as err:
        _print_errors(err)
        raise typer.Exit(1)
    total = cfg.agent["episodes"]
    checkpoints = default_checkpoints(total)
    run_dir = create_run_dir(cfg, runs_dir)
    git = git_info()
    base_meta = {"experiment": cfg.name, "mission": cfg.mission, "total_episodes": total,
                 "config": cfg.raw, "git": git, "run_dir": str(run_dir)}
    console.print(f"[bold]Entrenando[/] {cfg.name} · misión {cfg.mission} · {total} episodios · "
                  f"Q-table {env.q_table_shape[0]}×{env.q_table_shape[1]} · checkpoints {checkpoints}")

    checkpoint_rows: list[dict] = []

    def on_checkpoint(k: int, agent: QLearningAgent) -> None:
        model_path = models_dir / f"{cfg.name}_ep{k:05d}.npz"
        agent.save(model_path, {**base_meta, "trained_episodes": k})
        recorder = EpisodeRecorder(make_env(cfg), out_dir=run_dir / "episodes", auto_save=False, label=f"ep{k}",
                                   metadata={"agent": "q_learning", "model": model_path.name, "trained_episodes": k,
                                             "total_episodes": total, "training_progress": k / total})
        result = run_greedy(agent, recorder, seed=0)
        episode_path = recorder.save(run_dir / "episodes" / f"{cfg.name}_ep{k:05d}.json")
        if export:
            DEFAULT_EPISODES_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy(episode_path, DEFAULT_EPISODES_DIR / f"{run_dir.name}_ep{k:05d}.json")
        checkpoint_rows.append({"label": k, "model": str(model_path), "episode": str(episode_path), **result})

    started = time.perf_counter()
    with Progress(
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("{task.fields[stats]}"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("episodios", total=total, stats="")

        def on_episode(stats, history) -> None:
            if stats.episode % 25 == 0 or stats.episode == total:
                progress.update(task, completed=stats.episode, stats=(
                    f"R̄₁₀₀ {history.mean_reward():+7.1f} · éxito₁₀₀ {history.success_rate() * 100:5.1f} % · "
                    f"pasos₁₀₀ {history.mean_steps():5.0f} · ε {stats.epsilon:.2f}"))

        agent, history = train(env, on_episode, checkpoints=checkpoints, on_checkpoint=on_checkpoint)
    duration = time.perf_counter() - started

    final_path = agent.save(models_dir / f"{cfg.name}.npz", {**base_meta, "trained_episodes": total})
    write_metrics_csv(run_dir, history.episodes)
    write_run_summary(run_dir, {
        "experiment": cfg.name,
        "mission": cfg.mission,
        "git": git,
        "agent": cfg.agent,
        "episodes": total,
        "duration_s": round(duration, 1),
        "final_window": {"mean_reward": history.mean_reward(), "success_rate": history.success_rate(),
                         "mean_steps": history.mean_steps()},
        "model": str(final_path),
        "checkpoints": checkpoint_rows,
    })

    console.print(_result_table("Cómo aprende · política greedy en cada checkpoint", checkpoint_rows,
                                "Episodios entrenados"))
    console.print(f"Modelo: [bold]{final_path}[/] · corrida: [bold]{run_dir}[/] · {duration:.0f} s")
    console.print(f"Ver el modelo: [cyan]robot-exp watch --model {final_path}[/]")


def _load_model(model: Path, config: Optional[Path]) -> tuple[QLearningAgent, dict, ExperimentConfig]:
    try:
        agent, meta = QLearningAgent.load(model)
    except (ValueError, OSError, KeyError) as err:
        console.print(f"[red]No se pudo cargar el modelo {model}: {err}[/]")
        raise typer.Exit(1)
    try:
        cfg = load_config(config if config else meta["config"])
    except ConfigError as err:
        _print_errors(err)
        raise typer.Exit(1)
    return agent, meta, cfg


@app.command()
def watch(
    model: Path = typer.Option(..., "--model", "-m", exists=True, dir_okay=False, help="Q-table (.npz)."),
    config: Optional[Path] = typer.Option(None, "--config", "-c", exists=True, dir_okay=False,
                                          help="YAML (por defecto, el guardado con el modelo)."),
    incident: Optional[str] = typer.Option(None, help="none | blocked_corridor (por defecto, el del YAML)."),
    fps: float = typer.Option(4.0, min=0.1, help="Frames por segundo."),
    final_only: bool = typer.Option(False, "--final-only", help="Mostrar solo el último frame."),
    save: bool = typer.Option(True, "--save/--no-save", help="Guardar el episodio para el visor."),
    live: bool = typer.Option(False, "--live", help="Mostrarlo también en el visor three.js."),
    live_port: int = typer.Option(DEFAULT_LIVE_PORT, help="Puerto WebSocket del modo --live."),
    viewer_url: str = typer.Option("http://localhost:5173", help="URL del visor."),
    open_viewer: bool = typer.Option(True, "--open/--no-open", help="Abrir el visor en el navegador con --live."),
) -> None:
    """Corre el agente entrenado (política greedy) y exporta el episodio para el visor."""
    agent, meta, cfg = _load_model(model, config)
    try:
        env = make_env(cfg, incident=_parse_incident(incident, cfg))
    except ConfigError as err:
        _print_errors(err)
        raise typer.Exit(1)
    if env.q_table_shape != agent.q.shape:
        console.print(f"[red]El modelo {agent.q.shape} no corresponde a este ambiente {env.q_table_shape}.[/]")
        raise typer.Exit(1)

    trained = meta.get("trained_episodes", 0)
    total = meta.get("total_episodes", trained) or 1
    recorder = EpisodeRecorder(env, auto_save=False, label=f"watch_{model.stem}",
                               metadata={"agent": "q_learning", "model": model.name, "trained_episodes": trained,
                                         "total_episodes": total, "training_progress": trained / total})
    result = run_greedy(agent, recorder, seed=0)
    data = recorder.to_dict()
    live_opts = {"port": live_port, "viewer_url": viewer_url, "open_viewer": open_viewer} if live else None
    _animate(data, f"{model.name} · {trained} episodios", "ROBOT EXPEDITION · agente", fps, final_only, live_opts)
    if save:
        console.print(f"Episodio guardado en [bold]{recorder.save()}[/]")
    console.print(_result_table("Resultado", [{"label": model.name, **result}], "Modelo"))


@app.command()
def evaluate(
    model: Path = typer.Option(..., "--model", "-m", exists=True, dir_okay=False, help="Q-table (.npz)."),
    config: Optional[Path] = typer.Option(None, "--config", "-c", exists=True, dir_okay=False,
                                          help="YAML (por defecto, el guardado con el modelo)."),
    seeds: int = typer.Option(5, min=1, help="Episodios por condición (cambia el ruido de los sensores)."),
) -> None:
    """Misiones completas, balizas, batería, recorrido y colisiones, con y sin incidente."""
    agent, _, cfg = _load_model(model, config)
    conditions: list[Optional[str]] = [None]
    if cfg.map.get("seed") is None and cfg.map.get("blocked_corridor"):
        conditions.append("blocked_corridor")
    rows = []
    for inc in conditions:
        env = make_env(cfg, incident=inc)
        results = [run_greedy(agent, env, seed=s) for s in range(seeds)]
        rows.append({
            "label": inc or "sin incidente",
            "success": all(r["success"] for r in results),
            "visited": sorted({v for r in results for v in r["visited"]}),
            "steps": round(sum(r["steps"] for r in results) / seeds),
            "path_length": round(sum(r["path_length"] for r in results) / seeds),
            "collisions": round(sum(r["collisions"] for r in results) / seeds, 1),
            "battery_fraction": sum(r["battery_fraction"] for r in results) / seeds,
            "reward": sum(r["reward"] for r in results) / seeds,
            "rate": sum(r["success"] for r in results) / seeds,
        })
    table = _result_table(f"Evaluación · {model.name} · {seeds} episodios por condición", rows, "Condición")
    console.print(table)
    for row in rows:
        console.print(f"  {row['label']}: misiones completas {row['rate'] * 100:.0f} %")


if __name__ == "__main__":
    app()
