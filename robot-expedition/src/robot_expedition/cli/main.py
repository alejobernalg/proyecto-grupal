"""Punto de entrada del CLI `robot-exp`. Los comandos se agregan en la Fase 3."""

import typer
from rich.console import Console

from robot_expedition import __version__

app = typer.Typer(help="ROBOT EXPEDITION: CLI del ambiente de RL.", no_args_is_help=True)
console = Console()


@app.callback()
def main() -> None:
    """ROBOT EXPEDITION: CLI del ambiente de RL."""


@app.command()
def version() -> None:
    """Muestra la versión instalada."""
    console.print(f"robot-expedition [bold cyan]{__version__}[/]")


if __name__ == "__main__":
    app()
