"""Trazabilidad de corridas: cada entrenamiento guarda config, commit, métricas y episodios
en ``data/runs/<fecha>_<experimento>/``."""

from __future__ import annotations

import csv
import json
import subprocess
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import yaml

from robot_expedition.config import PROJECT_ROOT, ExperimentConfig

RUNS_DIR = PROJECT_ROOT / "data" / "runs"


def git_info() -> dict[str, Any]:
    def run(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True).stdout.strip()

    try:
        return {"commit": run("rev-parse", "HEAD"), "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
                "dirty": bool(run("status", "--porcelain", "--", "."))}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "branch": None, "dirty": None}


def create_run_dir(config: ExperimentConfig, root: Path = RUNS_DIR) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = root / f"{stamp}_{config.name}"
    (run_dir / "episodes").mkdir(parents=True, exist_ok=True)
    (run_dir / "config.yaml").write_text(
        yaml.safe_dump(config.raw, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return run_dir


def write_run_summary(run_dir: Path, summary: dict[str, Any]) -> None:
    (run_dir / "run.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def write_metrics_csv(run_dir: Path, rows: Iterable[Any]) -> None:
    rows = [asdict(r) for r in rows]
    if not rows:
        return
    with (run_dir / "metrics.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
