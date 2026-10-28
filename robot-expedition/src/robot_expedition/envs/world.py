"""Mundo en grilla: mapa, validación con BFS y generación de mapas aleatorios.

Convenciones:
- Cada celda mide 1 m. La grilla es de ``size × size`` y su borde es pared.
- ``x`` crece hacia el este (columnas) e ``y`` hacia el sur (filas); (0, 0) es la esquina noroeste.
- Las matrices se indexan ``[y, x]``.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np

from robot_expedition.config import ConfigError

ORIENTATIONS = ("N", "E", "S", "O")
# Vector unitario (dx, dy) de cada orientación.
DIRECTIONS = ((0, -1), (1, 0), (0, 1), (-1, 0))
TARGETS = ("beacon_1", "beacon_2", "base")
OBSTACLE_KINDS = ("orange", "coral", "gray")
UNREACHABLE = -1


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int
    kind: str = "gray"

    @classmethod
    def from_dict(cls, data: dict[str, Any], kind: str = "gray") -> Rect:
        return cls(int(data["x"]), int(data["y"]), int(data["w"]), int(data["h"]), str(data.get("kind", kind)))

    def cells(self) -> list[tuple[int, int]]:
        return [(cx, cy) for cy in range(self.y, self.y + self.h) for cx in range(self.x, self.x + self.w)]

    def contains(self, x: int, y: int) -> bool:
        return self.x <= x < self.x + self.w and self.y <= y < self.y + self.h

    def gap(self, other: Rect) -> int:
        """Celdas libres entre dos rectángulos (0 si se tocan o se solapan)."""
        gx = max(other.x - (self.x + self.w), self.x - (other.x + other.w), 0)
        gy = max(other.y - (self.y + self.h), self.y - (other.y + other.h), 0)
        return max(gx, gy)

    def wall_gaps(self, size: int) -> tuple[int, int, int, int]:
        return (self.x, self.y, size - (self.x + self.w), size - (self.y + self.h))

    def in_bounds(self, size: int) -> bool:
        return self.w >= 1 and self.h >= 1 and min(self.wall_gaps(size)) >= 0

    def to_dict(self) -> dict[str, Any]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h, "kind": self.kind}


@dataclass
class World:
    size: int
    obstacles: tuple[Rect, ...]
    base: Rect
    beacons: tuple[tuple[int, int], tuple[int, int]]
    start: tuple[int, int, int]
    blocked_corridor: Rect | None
    incident: str | None
    seed: int | None
    occupied: np.ndarray
    distances: dict[str, np.ndarray]

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.size and 0 <= y < self.size

    def is_free(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and not self.occupied[y, x]

    def target_cells(self, target: str) -> list[tuple[int, int]]:
        if target == "base":
            return self.base.cells()
        return [self.beacons[TARGETS.index(target)]]

    def target_center(self, target: str) -> tuple[float, float]:
        if target == "base":
            return (self.base.x + self.base.w / 2, self.base.y + self.base.h / 2)
        bx, by = self.beacons[TARGETS.index(target)]
        return (bx + 0.5, by + 0.5)

    def distance(self, target: str, x: int, y: int) -> int:
        """Distancia BFS (en celdas = metros) desde (x, y) hasta el objetivo."""
        return int(self.distances[target][y, x])

    def to_dict(self) -> dict[str, Any]:
        return {
            "size": self.size,
            "cell_size_m": 1.0,
            "axes": "x hacia el este, y hacia el sur; (0, 0) = esquina noroeste",
            "obstacles": [r.to_dict() for r in self.obstacles],
            "blocked": [self.blocked_corridor.to_dict()] if self.incident == "blocked_corridor" else [],
            "base": self.base.to_dict(),
            "beacons": [{"id": i + 1, "x": bx, "y": by} for i, (bx, by) in enumerate(self.beacons)],
            "start": {"x": self.start[0], "y": self.start[1], "orientation": ORIENTATIONS[self.start[2]]},
            "incident": self.incident,
            "seed": self.seed,
        }


def bfs_distances(occupied: np.ndarray, sources: list[tuple[int, int]]) -> np.ndarray:
    """Distancia BFS (4 vecinos) desde el conjunto ``sources`` a cada celda; -1 si no hay ruta."""
    size_y, size_x = occupied.shape
    dist = np.full(occupied.shape, UNREACHABLE, dtype=np.int32)
    queue: deque[tuple[int, int]] = deque()
    for x, y in sources:
        if not occupied[y, x]:
            dist[y, x] = 0
            queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for dx, dy in DIRECTIONS:
            nx, ny = x + dx, y + dy
            if 0 <= nx < size_x and 0 <= ny < size_y and not occupied[ny, nx] and dist[ny, nx] == UNREACHABLE:
                dist[ny, nx] = dist[y, x] + 1
                queue.append((nx, ny))
    return dist


def build_world(map_cfg: dict[str, Any], env_params: dict[str, Any], incident: str | None) -> World:
    """Construye y valida el mundo. Con ``map.seed`` entero genera un mapa aleatorio válido."""
    size = env_params["map_size"]
    corridor_width = env_params["corridor_width"]
    seed = map_cfg.get("seed")
    if seed is None:
        return _build_from_dict(map_cfg, size, corridor_width, incident, seed=None)
    if incident is not None:
        raise ConfigError("incident: los mapas aleatorios no definen pasillo bloqueable; usa seed: null")
    return generate_random_world(size, corridor_width, int(map_cfg.get("num_obstacles", 6)), int(seed))


def generate_random_world(size: int, corridor_width: int, num_obstacles: int, seed: int,
                          max_attempts: int = 500) -> World:
    """Genera un mapa aleatorio que cumple las mismas validaciones que el mapa fijo."""
    rng = np.random.default_rng(seed)
    last_error: ConfigError | None = None
    for _ in range(max_attempts):
        map_cfg = _random_map_dict(rng, size, corridor_width, num_obstacles)
        if map_cfg is None:
            continue
        try:
            return _build_from_dict(map_cfg, size, corridor_width, None, seed=seed)
        except ConfigError as err:
            last_error = err
    raise ConfigError(f"No se pudo generar un mapa válido con seed={seed} tras {max_attempts} intentos: {last_error}")


def _random_map_dict(rng: np.random.Generator, size: int, corridor_width: int,
                     num_obstacles: int) -> dict[str, Any] | None:
    obstacles: list[Rect] = []
    for _ in range(num_obstacles * 30):
        if len(obstacles) == num_obstacles:
            break
        w, h = (int(v) for v in rng.integers(1, 4, size=2))
        x, y = int(rng.integers(0, size - w + 1)), int(rng.integers(0, size - h + 1))
        rect = Rect(x, y, w, h, str(rng.choice(OBSTACLE_KINDS)))
        if _spacing_errors(rect, obstacles, size, corridor_width):
            continue
        obstacles.append(rect)

    occupied = _occupancy(size, obstacles)
    bw, bh = 2, 2
    bx, by = int(rng.integers(0, size - bw + 1)), int(rng.integers(0, size - bh + 1))
    base = Rect(bx, by, bw, bh, "base")
    if any(occupied[cy, cx] for cx, cy in base.cells()):
        return None

    free = [(x, y) for y in range(size) for x in range(size) if not occupied[y, x] and not base.contains(x, y)]
    if len(free) < 2:
        return None
    min_sep = max(2, size // 3)
    picks = rng.permutation(len(free))
    beacons: list[tuple[int, int]] = []
    for i in picks:
        cx, cy = free[i]
        far_from_base = abs(cx - bx) + abs(cy - by) >= min_sep
        far_from_others = all(abs(cx - ox) + abs(cy - oy) >= min_sep for ox, oy in beacons)
        if far_from_base and far_from_others:
            beacons.append((cx, cy))
            if len(beacons) == 2:
                break
    if len(beacons) < 2:
        return None

    return {
        "base": base.to_dict(),
        "start": {"x": bx, "y": by, "orientation": ORIENTATIONS[int(rng.integers(0, 4))]},
        "beacons": [{"id": i + 1, "x": x, "y": y} for i, (x, y) in enumerate(beacons)],
        "obstacles": [r.to_dict() for r in obstacles],
    }


def _occupancy(size: int, rects: list[Rect]) -> np.ndarray:
    occupied = np.zeros((size, size), dtype=bool)
    for rect in rects:
        occupied[rect.y:rect.y + rect.h, rect.x:rect.x + rect.w] = True
    return occupied


def _spacing_errors(rect: Rect, others: list[Rect], size: int, corridor_width: int) -> list[str]:
    """Un obstáculo debe tocar la pared o dejar al menos ``corridor_width`` de pasillo, y lo mismo entre obstáculos."""
    errors = []
    if not rect.in_bounds(size):
        return [f"obstáculo {rect.to_dict()} sale de la sala"]
    narrow = [g for g in rect.wall_gaps(size) if 0 < g < corridor_width]
    if narrow:
        errors.append(f"obstáculo {rect.to_dict()} deja un pasillo de {min(narrow)} m contra la pared (< {corridor_width} m)")
    for other in others:
        if rect.gap(other) < corridor_width:
            errors.append(f"obstáculos {rect.to_dict()} y {other.to_dict()} separados {rect.gap(other)} m (< {corridor_width} m)")
    return errors


def _build_from_dict(map_cfg: dict[str, Any], size: int, corridor_width: int, incident: str | None,
                     seed: int | None) -> World:
    errors: list[str] = []
    try:
        obstacles = [Rect.from_dict(o) for o in map_cfg.get("obstacles", [])]
        base = Rect.from_dict(map_cfg["base"], "base")
        beacon_list = sorted(map_cfg["beacons"], key=lambda b: b["id"])
        start_cfg = map_cfg["start"]
        blocked_cfg = map_cfg.get("blocked_corridor")
        blocked = Rect.from_dict(blocked_cfg, "blocked") if blocked_cfg else None
    except (KeyError, TypeError, ValueError) as err:
        raise ConfigError(f"map: estructura inválida ({err!r})") from err

    if [b["id"] for b in beacon_list] != [1, 2]:
        raise ConfigError("map.beacons: deben existir exactamente las balizas 1 y 2")
    beacons = tuple((int(b["x"]), int(b["y"])) for b in beacon_list)
    orientation = start_cfg.get("orientation")
    if orientation not in ORIENTATIONS:
        raise ConfigError(f"map.start.orientation: '{orientation}' no es una de {ORIENTATIONS}")
    start = (int(start_cfg["x"]), int(start_cfg["y"]), ORIENTATIONS.index(orientation))

    # Separaciones y límites de obstáculos.
    for i, rect in enumerate(obstacles):
        errors.extend(_spacing_errors(rect, obstacles[:i], size, corridor_width))
    if not base.in_bounds(size):
        errors.append("map.base: sale de la sala")

    occupied = _occupancy(size, [r for r in obstacles if r.in_bounds(size)])

    def check_cell(label: str, x: int, y: int) -> None:
        if not (0 <= x < size and 0 <= y < size):
            errors.append(f"{label}: ({x}, {y}) está fuera de la sala")
        elif occupied[y, x]:
            errors.append(f"{label}: ({x}, {y}) está dentro de un obstáculo")

    for i, (bx, by) in enumerate(beacons):
        check_cell(f"map.beacons[{i + 1}]", bx, by)
        if base.contains(bx, by):
            errors.append(f"map.beacons[{i + 1}]: no puede estar dentro de la base")
    if beacons[0] == beacons[1]:
        errors.append("map.beacons: las dos balizas ocupan la misma celda")
    for cx, cy in base.cells():
        check_cell("map.base", cx, cy)
    check_cell("map.start", start[0], start[1])
    if not base.contains(start[0], start[1]):
        errors.append("map.start: el robot debe empezar dentro de la base")

    if incident == "blocked_corridor":
        if blocked is None:
            errors.append("incident blocked_corridor: falta map.blocked_corridor")
        elif not blocked.in_bounds(size):
            errors.append("map.blocked_corridor: sale de la sala")
        else:
            protected = [*beacons, *base.cells()]
            if any(blocked.contains(x, y) for x, y in protected):
                errors.append("map.blocked_corridor: no puede tapar balizas ni la base")
            occupied = occupied | _occupancy(size, [blocked])

    if errors:
        raise ConfigError(errors)

    distances = {
        "beacon_1": bfs_distances(occupied, [beacons[0]]),
        "beacon_2": bfs_distances(occupied, [beacons[1]]),
        "base": bfs_distances(occupied, base.cells()),
    }
    # Ruta obligatoria: base → baliza 1 → baliza 2 → base.
    legs = [
        ("base → baliza 1", distances["beacon_1"][start[1], start[0]]),
        ("baliza 1 → baliza 2", distances["beacon_2"][beacons[0][1], beacons[0][0]]),
        ("baliza 2 → base", distances["base"][beacons[1][1], beacons[1][0]]),
    ]
    missing = [name for name, d in legs if d == UNREACHABLE]
    if missing:
        raise ConfigError([f"no hay ruta {name}" + (" (con el incidente activo)" if incident else "") for name in missing])

    return World(
        size=size,
        obstacles=tuple(obstacles),
        base=base,
        beacons=beacons,  # type: ignore[arg-type]
        start=start,
        blocked_corridor=blocked,
        incident=incident,
        seed=seed,
        occupied=occupied,
        distances=distances,
    )
