"""Carga y validación de la configuración de un experimento (YAML).

Cada parámetro se declara en el YAML como ``{value, unit, range: [mín, máx]}``.
Al cargar se comprueba que:

- la unidad coincida con la que espera el simulador,
- el rango declarado quepa dentro de los límites duros del simulador,
- el valor tenga el tipo correcto y esté dentro del rango declarado.

La validación del mapa (rutas, separaciones) vive en ``envs.world``.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "experimento_1.yaml"
INCIDENTS = (None, "blocked_corridor")
# full: base → baliza 1 → baliza 2 → base. a_to_b: de la salida (A) a la baliza 1 (B).
MISSIONS = ("full", "a_to_b")


class ConfigError(ValueError):
    """Configuración inválida. ``errors`` lista todos los problemas encontrados."""

    def __init__(self, errors: list[str] | str):
        self.errors = [errors] if isinstance(errors, str) else list(errors)
        super().__init__("Configuración inválida:\n" + "\n".join(f"  - {e}" for e in self.errors))


@dataclass(frozen=True)
class ParamSpec:
    type: type
    unit: str
    min: float
    max: float
    help: str


# Límites duros del simulador. El rango del YAML debe caber dentro de estos.
PARAM_SPECS: dict[str, dict[str, ParamSpec]] = {
    "env": {
        "map_size": ParamSpec(int, "m × m", 4, 64, "Lado de la sala cuadrada; cada celda mide 1 m"),
        "corridor_width": ParamSpec(int, "m", 1, 10, "Separación mínima entre obstáculos y con las paredes"),
        "max_speed": ParamSpec(int, "m/s", 1, 3, "Celdas que recorre 'avanzar' en un paso (1 paso = 1 s)"),
        "distance_noise_std": ParamSpec(float, "m", 0.0, 2.0, "Desviación estándar del ruido de los rayos"),
        "sensor_range": ParamSpec(float, "m", 1.0, 30.0, "Alcance máximo de los rayos"),
        "battery_capacity": ParamSpec(float, "u", 1.0, 10_000.0, "Batería inicial"),
        "battery_cost_forward": ParamSpec(float, "u/acción", 0.0, 100.0, "Consumo de avanzar"),
        "battery_cost_backward": ParamSpec(float, "u/acción", 0.0, 100.0, "Consumo de retroceder"),
        "battery_cost_turn": ParamSpec(float, "u/acción", 0.0, 100.0, "Consumo de girar"),
        "battery_cost_stay": ParamSpec(float, "u/acción", 0.0, 100.0, "Consumo de quedarse"),
        "max_steps": ParamSpec(int, "pasos", 1, 100_000, "Pasos antes de truncar el episodio"),
    },
    "reward": {
        "progress_weight": ParamSpec(float, "pts/m", 0.0, 100.0, "Peso del shaping por potencial"),
        "shaping_gamma": ParamSpec(float, "adim", 0.0, 1.0, "γ en r = γ·Φ(s') − Φ(s)"),
        "beacon_bonus": ParamSpec(float, "pts", 0.0, 10_000.0, "Bono por baliza (primera vez y en orden)"),
        "return_bonus": ParamSpec(float, "pts", 0.0, 10_000.0, "Bono por volver a la base con ambas balizas"),
        "time_penalty": ParamSpec(float, "pts/paso", 0.0, 100.0, "Costo fijo por paso"),
        "battery_penalty": ParamSpec(float, "pts/u", 0.0, 100.0, "Costo por unidad de batería consumida"),
        "collision_penalty": ParamSpec(float, "pts/choque", 0.0, 1_000.0, "Costo por colisión"),
        "depletion_penalty": ParamSpec(float, "pts", 0.0, 10_000.0, "Costo por agotar la batería"),
    },
    "wrapper": {
        "battery_levels": ParamSpec(int, "niveles", 1, 100, "Niveles k de batería en DiscreteStateWrapper"),
    },
    "agent": {
        "alpha": ParamSpec(float, "adim", 0.0, 1.0, "Tasa de aprendizaje α de Q-learning"),
        "gamma": ParamSpec(float, "adim", 0.0, 1.0, "Factor de descuento γ del agente"),
        "epsilon_start": ParamSpec(float, "adim", 0.0, 1.0, "ε inicial de ε-greedy"),
        "epsilon_end": ParamSpec(float, "adim", 0.0, 1.0, "ε final de ε-greedy"),
        "epsilon_decay_fraction": ParamSpec(float, "adim", 0.0, 1.0, "Fracción de episodios en que ε baja linealmente"),
        "episodes": ParamSpec(int, "episodios", 1, 1_000_000, "Episodios de entrenamiento"),
        "seed": ParamSpec(int, "adim", 0, 2**31 - 1, "Semilla del entrenamiento"),
    },
}


@dataclass
class ExperimentConfig:
    """Configuración validada. ``env``, ``reward`` y ``wrapper`` guardan solo los valores."""

    name: str
    env: dict[str, Any]
    reward: dict[str, Any]
    wrapper: dict[str, Any]
    agent: dict[str, Any]
    map: dict[str, Any]
    incident: str | None
    mission: str
    raw: dict[str, Any]
    source: Path | None = None

    def param_rows(self) -> list[dict[str, Any]]:
        """Filas (sección, parámetro, valor, unidad, rango, descripción) para mostrar en tablas."""
        rows = []
        for section, specs in PARAM_SPECS.items():
            for name, spec in specs.items():
                entry = self.raw[section][name]
                rows.append(
                    {
                        "section": section,
                        "name": name,
                        "value": entry["value"],
                        "unit": entry["unit"],
                        "range": list(entry["range"]),
                        "help": spec.help,
                    }
                )
        return rows


def load_config(source: str | Path | Mapping[str, Any] | ExperimentConfig | None = None) -> ExperimentConfig:
    """Carga y valida una configuración desde un YAML, un dict o la config por defecto."""
    if isinstance(source, ExperimentConfig):
        return source
    if source is None:
        source = DEFAULT_CONFIG_PATH

    path: Path | None = None
    if isinstance(source, (str, Path)):
        path = Path(source)
        raw = _read_yaml(path)
    else:
        raw = deepcopy(dict(source))
    if not isinstance(raw, dict):
        raise ConfigError("El YAML debe ser un diccionario en la raíz")

    errors: list[str] = []
    values = {section: _validate_section(raw, section, specs, errors) for section, specs in PARAM_SPECS.items()}

    name = raw.get("experiment")
    if not isinstance(name, str) or not name:
        errors.append("experiment: falta el nombre del experimento")
    incident = raw.get("incident")
    if incident not in INCIDENTS:
        errors.append(f"incident: '{incident}' no es válido; opciones: {INCIDENTS}")
    mission = raw.setdefault("mission", "full")
    if mission not in MISSIONS:
        errors.append(f"mission: '{mission}' no es válida; opciones: {MISSIONS}")
    map_cfg = raw.get("map")
    if not isinstance(map_cfg, dict):
        errors.append("map: falta la sección del mapa")

    if errors:
        raise ConfigError(errors)
    return ExperimentConfig(
        name=name,
        env=values["env"],
        reward=values["reward"],
        wrapper=values["wrapper"],
        agent=values["agent"],
        map=map_cfg,
        incident=incident,
        mission=mission,
        raw=raw,
        source=path,
    )


def _read_yaml(path: Path, seen: tuple[Path, ...] = ()) -> dict[str, Any]:
    """Lee un YAML. Con ``extends: otro.yaml`` hereda de ese archivo y sobrescribe solo lo que declara."""
    if not path.exists():
        raise ConfigError(f"No existe el archivo de configuración: {path}")
    if path.resolve() in seen:
        raise ConfigError(f"extends circular en {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: el YAML debe ser un diccionario en la raíz")
    parent = raw.pop("extends", None)
    if parent is None:
        return raw
    base = _read_yaml(path.parent / parent, (*seen, path.resolve()))
    return _deep_merge(base, raw)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_section(raw: dict, section: str, specs: dict[str, ParamSpec], errors: list[str]) -> dict[str, Any]:
    block = raw.get(section)
    if not isinstance(block, dict):
        errors.append(f"{section}: falta la sección")
        return {}

    out: dict[str, Any] = {}
    for unknown in sorted(set(block) - set(specs)):
        errors.append(f"{section}.{unknown}: parámetro desconocido")
    for name, spec in specs.items():
        key = f"{section}.{name}"
        entry = block.get(name)
        if not isinstance(entry, dict) or not {"value", "unit", "range"} <= set(entry):
            errors.append(f"{key}: debe declararse como {{value, unit, range}}")
            continue
        value, unit, rng = entry["value"], entry["unit"], entry["range"]

        if unit != spec.unit:
            errors.append(f"{key}: unidad '{unit}', se esperaba '{spec.unit}'")
        if not (isinstance(rng, (list, tuple)) and len(rng) == 2 and all(_is_number(r) for r in rng)):
            errors.append(f"{key}: range debe ser [mín, máx]")
            continue
        lo, hi = rng
        if lo > hi:
            errors.append(f"{key}: range [{lo}, {hi}] tiene mín > máx")
            continue
        if lo < spec.min or hi > spec.max:
            errors.append(f"{key}: range [{lo}, {hi}] sale de los límites del simulador [{spec.min}, {spec.max}]")

        if spec.type is int and not (isinstance(value, int) and not isinstance(value, bool)):
            errors.append(f"{key}: el valor {value!r} debe ser entero")
            continue
        if not _is_number(value):
            errors.append(f"{key}: el valor {value!r} debe ser numérico")
            continue
        if not lo <= value <= hi:
            errors.append(f"{key}: valor {value} {spec.unit} fuera del rango [{lo}, {hi}]")
            continue
        out[name] = spec.type(value)
    return out
