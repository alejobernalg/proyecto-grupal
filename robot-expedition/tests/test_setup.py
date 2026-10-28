"""Verifica que el entorno de la Fase 0 está bien instalado."""

from typer.testing import CliRunner


def test_dependencies_import():
    import gymnasium
    import numpy
    import rich
    import typer
    import yaml

    assert gymnasium.__version__


def test_cli_version():
    from robot_expedition.cli.main import app

    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert "robot-expedition" in result.output
