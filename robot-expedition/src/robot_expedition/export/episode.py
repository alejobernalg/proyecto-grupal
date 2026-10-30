"""Grabación de episodios como lista de frames JSON (para el visor y como dataset)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import gymnasium as gym

from robot_expedition.config import PROJECT_ROOT

EPISODE_FORMAT = "robot-expedition/episode@1"
DEFAULT_EPISODES_DIR = PROJECT_ROOT / "data" / "episodes"


class EpisodeRecorder(gym.Wrapper):
    """Guarda un frame por paso (incluido el inicial) y escribe el episodio al terminar.

    El archivo tiene la forma ``{"format", "experiment", "created", "map", "params", "frames": [...]}``;
    el mapa va una sola vez en la cabecera y cada frame trae el resto del estado.
    """

    def __init__(self, env: gym.Env, out_dir: str | Path = DEFAULT_EPISODES_DIR, auto_save: bool = True,
                 label: str = "episode", metadata: dict[str, Any] | None = None):
        super().__init__(env)
        self.out_dir = Path(out_dir)
        self.auto_save = auto_save
        self.label = label
        self.metadata = metadata or {}
        self.frames: list[dict[str, Any]] = []
        self.saved_path: Path | None = None

    def reset(self, **kwargs):
        obs, info = self.env.reset(**kwargs)
        self.frames = [self.env.unwrapped.export_frame(include_map=False)]
        self.saved_path = None
        return obs, info

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        frame = self.env.unwrapped.export_frame(include_map=False)
        frame["action"] = int(action)
        self.frames.append(frame)
        if (terminated or truncated) and self.auto_save:
            self.save()
        return obs, reward, terminated, truncated, info

    def to_dict(self) -> dict[str, Any]:
        base = self.env.unwrapped
        return {
            "format": EPISODE_FORMAT,
            "experiment": base.config.name,
            "created": datetime.now().isoformat(timespec="seconds"),
            "actions": list(base.ACTION_NAMES),
            "map": base.world.to_dict(),
            "params": {"env": base.config.env, "reward": base.config.reward},
            "metadata": self.metadata,
            "frames": self.frames,
        }

    def save(self, path: str | Path | None = None) -> Path:
        if path is None:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            path = self.out_dir / f"{stamp}_{self.env.unwrapped.config.name}_{self.label}.json"
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
        self.saved_path = path
        return path


def load_episode(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != EPISODE_FORMAT:
        raise ValueError(f"{path} no es un episodio {EPISODE_FORMAT}")
    return data
