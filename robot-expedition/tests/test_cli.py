import yaml
from typer.testing import CliRunner

from robot_expedition.cli.main import app
from robot_expedition.config import DEFAULT_CONFIG_PATH, PROJECT_ROOT
from robot_expedition.export.episode import load_episode

runner = CliRunner()
EXAMPLE = PROJECT_ROOT / "data" / "examples" / "oracle_experimento_1.json"


def test_validate_config_ok():
    result = runner.invoke(app, ["validate-config", str(DEFAULT_CONFIG_PATH)])
    assert result.exit_code == 0, result.output
    assert "Configuración válida" in result.output
    assert "6912 estados" in result.output


def test_validate_config_reports_errors(tmp_path):
    raw = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    raw["env"]["map_size"]["value"] = 50
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    result = runner.invoke(app, ["validate-config", str(bad)])
    assert result.exit_code == 1
    assert "map_size" in result.output


def test_play_with_keys_saves_episode(tmp_path):
    result = runner.invoke(app, ["play", "--keys", "wdwwwq", "--out-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    saved = list(tmp_path.glob("*.json"))
    assert len(saved) == 1
    episode = load_episode(saved[0])
    assert len(episode["frames"]) == 6  # inicial + 5 acciones (la q no es acción)
    assert episode["metadata"]["ended_by"] == "quit"
    assert episode["frames"][-1]["collisions"] == 1


def test_play_without_terminal_requires_keys():
    result = runner.invoke(app, ["play", "--no-save"])
    assert result.exit_code == 2


def test_play_rejects_unknown_incident():
    result = runner.invoke(app, ["play", "--keys", "q", "--incident", "fire", "--no-save"])
    assert result.exit_code != 0


def test_replay_example_episode():
    result = runner.invoke(app, ["replay", str(EXAMPLE), "--final-only"])
    assert result.exit_code == 0, result.output
    assert "Misión completada sin colisiones" in result.output
