"""Ambiente Gymnasium ROBOT EXPEDITION.

Un robot debe visitar la baliza 1, luego la baliza 2 y volver a la base antes de agotar
la batería. Este módulo es la única fuente de verdad: colisiones, batería, reglas y
recompensas viven aquí. El CLI y el visor solo dibujan lo que devuelve ``export_frame()``.

Acciones (``Discrete(5)``)
    0 avanzar        recorre hasta ``max_speed`` celdas hacia el frente
    1 girar izquierda
    2 girar derecha
    3 retroceder     una celda hacia atrás, sin cambiar la orientación
    4 quedarse
    Moverse contra una pared u obstáculo es una colisión: el robot se queda en la última
    celda libre. Cada acción consume la batería configurada para ella.

Observación (``Dict``)
    rays              Box(9,)  distancias [m] a obstáculos/paredes en abanico frontal de
                               −90° (izquierda) a +90° (derecha) cada 22.5°, con ruido
                               gaussiano ``distance_noise_std``, recortadas a [0, sensor_range]
    target_direction  Box(2,)  vector unitario al objetivo actual en el marco del robot:
                               (frente, derecha)
    target_distance   Box(1,)  distancia BFS [m] al objetivo actual
    orientation       Discrete(4)  0 N, 1 E, 2 S, 3 O
    velocity          Box(1,)  celdas recorridas en el último paso (negativo = retroceso)
    turn              Box(1,)  último giro: −1 izquierda, 0 ninguno, +1 derecha
    battery           Box(1,)  batería normalizada en [0, 1]
    stage             Discrete(3)  0 → baliza 1, 1 → baliza 2, 2 → base

Recompensa (desglose en ``info["reward_breakdown"]``)
    progress   w·(γ·Φ(s') − Φ(s)) con Φ(s) = −(distancia BFS al objetivo actual +
               longitud BFS de los tramos que faltan). La constante por etapa hace que Φ
               no salte al cambiar de objetivo, así que ir y volver suma cero (con γ = 1).
    beacon     bono solo en la primera visita y solo si la baliza es el objetivo actual
    return     bono al volver a la base con ambas balizas
    time, battery, collision, depletion   penalizaciones
"""

from __future__ import annotations

import math
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from robot_expedition.config import ConfigError, ExperimentConfig, load_config
from robot_expedition.envs.world import DIRECTIONS, ORIENTATIONS, TARGETS, build_world

_FROM_CONFIG = object()


class RobotExpeditionEnv(gym.Env):
    metadata = {"render_modes": ["ansi"], "render_fps": 4}

    FORWARD, TURN_LEFT, TURN_RIGHT, BACKWARD, STAY = range(5)
    ACTION_NAMES = ("avanzar", "girar_izquierda", "girar_derecha", "retroceder", "quedarse")
    NUM_RAYS = 9
    RAY_ANGLES_DEG = np.linspace(-90.0, 90.0, NUM_RAYS)
    RAY_STEP = 0.05  # m, resolución del trazado de rayos
    REWARD_COMPONENTS = ("progress", "beacon", "return", "time", "battery", "collision", "depletion")

    def __init__(self, config: Any = None, render_mode: str | None = None, incident: Any = _FROM_CONFIG):
        self.config: ExperimentConfig = load_config(config)
        if incident is _FROM_CONFIG:
            incident = self.config.incident
        self.world = build_world(self.config.map, self.config.env, incident)

        env, rew = self.config.env, self.config.reward
        self.max_speed: int = env["max_speed"]
        self.noise_std: float = env["distance_noise_std"]
        self.sensor_range: float = env["sensor_range"]
        self.battery_capacity: float = env["battery_capacity"]
        self.max_steps: int = env["max_steps"]
        self.battery_costs = np.array(
            [
                env["battery_cost_forward"],
                env["battery_cost_turn"],
                env["battery_cost_turn"],
                env["battery_cost_backward"],
                env["battery_cost_stay"],
            ],
            dtype=np.float64,
        )
        self.rewards = dict(rew)

        w = self.world
        b1, b2 = w.beacons
        # Longitud BFS de los tramos que faltan después de alcanzar el objetivo de cada etapa.
        self._remaining_after = (
            w.distance("beacon_2", *b1) + w.distance("base", *b2),
            w.distance("base", *b2),
            0,
        )
        self._check_no_farming()

        n = w.size
        self.action_space = spaces.Discrete(5)
        self.observation_space = spaces.Dict(
            {
                "rays": spaces.Box(0.0, self.sensor_range, (self.NUM_RAYS,), np.float32),
                "target_direction": spaces.Box(-1.0, 1.0, (2,), np.float32),
                "target_distance": spaces.Box(0.0, float(n * n), (1,), np.float32),
                "orientation": spaces.Discrete(4),
                "velocity": spaces.Box(-float(self.max_speed), float(self.max_speed), (1,), np.float32),
                "turn": spaces.Box(-1.0, 1.0, (1,), np.float32),
                "battery": spaces.Box(0.0, 1.0, (1,), np.float32),
                "stage": spaces.Discrete(3),
            }
        )
        if render_mode is not None and render_mode not in self.metadata["render_modes"]:
            raise ValueError(f"render_mode '{render_mode}' no soportado; usa {self.metadata['render_modes']}")
        self.render_mode = render_mode

        self._ray_angles = np.deg2rad(self.RAY_ANGLES_DEG)
        self._ray_ts = np.arange(self.RAY_STEP, self.sensor_range + 1e-9, self.RAY_STEP)
        self._reset_state(w.start[:2], w.start[2])

    # ------------------------------------------------------------------ estado
    def _reset_state(self, pos: tuple[int, int], orientation: int) -> None:
        self.pos = (int(pos[0]), int(pos[1]))
        self.orientation = int(orientation)
        self.battery = float(self.battery_capacity)
        self.stage = 0
        self.visited: list[int] = []
        self.step_count = 0
        self.collisions = 0
        self.path_length = 0
        self.last_velocity = 0
        self.last_turn = 0
        self.total_reward = 0.0
        self.success = False
        self.terminated = False
        self.truncated = False
        self.last_reward = 0.0
        self.last_breakdown = {k: 0.0 for k in self.REWARD_COMPONENTS}
        self.last_events: list[str] = []
        self.last_rays = np.full(self.NUM_RAYS, self.sensor_range, dtype=np.float32)

    @property
    def target(self) -> str:
        return TARGETS[self.stage]

    # ------------------------------------------------------------------ API Gymnasium
    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        """Reinicia en la posición de salida. ``options`` admite ``position`` (x, y) y
        ``orientation`` ('N'|'E'|'S'|'O' o 0-3) para pruebas y escenarios."""
        super().reset(seed=seed)
        options = options or {}
        x, y, o = self.world.start
        if "position" in options:
            x, y = options["position"]
            if not self.world.is_free(x, y):
                raise ValueError(f"La posición inicial ({x}, {y}) no está libre")
        if "orientation" in options:
            o = options["orientation"]
            o = ORIENTATIONS.index(o) if isinstance(o, str) else int(o)
        self._reset_state((x, y), o)
        obs = self._observation()
        return obs, self._info()

    def step(self, action):
        action = int(action)
        if not self.action_space.contains(action):
            raise ValueError(f"Acción inválida: {action}")

        phi_before = self._potential()
        events: list[str] = []
        beacon_bonus = 0.0
        return_bonus = 0.0
        collided = False
        velocity = 0
        turn = 0

        if action in (self.FORWARD, self.BACKWARD):
            sign = 1 if action == self.FORWARD else -1
            cells = self.max_speed if action == self.FORWARD else 1
            dx, dy = DIRECTIONS[self.orientation]
            for _ in range(cells):
                nx, ny = self.pos[0] + sign * dx, self.pos[1] + sign * dy
                if not self.world.is_free(nx, ny):
                    collided = True
                    break
                self.pos = (nx, ny)
                velocity += sign
                bonus_b, bonus_r = self._arrive(events)
                beacon_bonus += bonus_b
                return_bonus += bonus_r
                if self.success:
                    break
        elif action == self.TURN_LEFT:
            self.orientation = (self.orientation - 1) % 4
            turn = -1
        elif action == self.TURN_RIGHT:
            self.orientation = (self.orientation + 1) % 4
            turn = 1

        if collided:
            self.collisions += 1
            events.append("collision")

        cost = float(self.battery_costs[action])
        self.battery = max(0.0, self.battery - cost)
        self.step_count += 1
        self.path_length += abs(velocity)
        self.last_velocity, self.last_turn = velocity, turn

        depleted = self.battery <= 0.0 and not self.success
        if depleted:
            events.append("battery_depleted")

        phi_after = self._potential()
        r = self.rewards
        breakdown = {
            "progress": r["progress_weight"] * (r["shaping_gamma"] * phi_after - phi_before),
            "beacon": beacon_bonus,
            "return": return_bonus,
            "time": -r["time_penalty"],
            "battery": -r["battery_penalty"] * cost,
            "collision": -r["collision_penalty"] if collided else 0.0,
            "depletion": -r["depletion_penalty"] if depleted else 0.0,
        }
        reward = float(sum(breakdown.values()))

        self.terminated = self.success or depleted
        self.truncated = not self.terminated and self.step_count >= self.max_steps
        self.total_reward += reward
        self.last_reward = reward
        self.last_breakdown = breakdown
        self.last_events = events

        obs = self._observation()
        return obs, reward, self.terminated, self.truncated, self._info()

    def render(self):
        if self.render_mode == "ansi":
            return self.render_ansi()
        return None

    # ------------------------------------------------------------------ reglas
    def _arrive(self, events: list[str]) -> tuple[float, float]:
        """Aplica las reglas al entrar en una celda. Devuelve (bono baliza, bono retorno)."""
        x, y = self.pos
        for i, beacon in enumerate(self.world.beacons):
            if beacon != (x, y):
                continue
            beacon_id = i + 1
            if beacon_id in self.visited:
                events.append(f"beacon_{beacon_id}_revisit")
            elif self.stage == i:
                self.visited.append(beacon_id)
                self.stage += 1
                events.append(f"beacon_{beacon_id}")
                return self.rewards["beacon_bonus"], 0.0
            else:
                events.append(f"beacon_{beacon_id}_out_of_order")
        if self.stage == 2 and self.world.base.contains(x, y):
            self.success = True
            events.append("mission_complete")
            return 0.0, self.rewards["return_bonus"]
        return 0.0, 0.0

    def _potential(self) -> float:
        x, y = self.pos
        return -float(self.world.distance(self.target, x, y) + self._remaining_after[self.stage])

    def _check_no_farming(self) -> None:
        """Rechaza configuraciones donde quedarse quieto o girar en el sitio dé recompensa positiva.

        Con γ < 1 el término de progreso al no moverse vale w·(1 − γ)·|Φ|, que puede superar
        las penalizaciones por paso lejos del objetivo.
        """
        r = self.rewards
        dist = self.world.distances["beacon_1"]
        max_remaining = float(dist[dist >= 0].max() + self._remaining_after[0])
        cheapest_idle = min(self.battery_costs[self.STAY], self.battery_costs[self.TURN_LEFT])
        idle_reward = (
            r["progress_weight"] * (1.0 - r["shaping_gamma"]) * max_remaining
            - r["time_penalty"]
            - r["battery_penalty"] * cheapest_idle
        )
        if idle_reward > 0:
            raise ConfigError(
                f"reward: quedarse quieto daría hasta +{idle_reward:.3f} por paso (se podría farmear). "
                "Sube time_penalty o acerca shaping_gamma a 1."
            )

    # ------------------------------------------------------------------ observación
    def _cast_rays(self) -> np.ndarray:
        x, y = self.pos
        hx, hy = DIRECTIONS[self.orientation]
        rx, ry = -hy, hx  # vector a la derecha del robot
        cos_a, sin_a = np.cos(self._ray_angles), np.sin(self._ray_angles)
        dirs = np.stack([cos_a * hx + sin_a * rx, cos_a * hy + sin_a * ry], axis=1)  # (9, 2)
        pts = np.array([x + 0.5, y + 0.5]) + self._ray_ts[None, :, None] * dirs[:, None, :]
        cells = np.floor(pts).astype(np.int64)
        cx, cy = cells[..., 0], cells[..., 1]
        n = self.world.size
        inside = (cx >= 0) & (cx < n) & (cy >= 0) & (cy < n)
        blocked = ~inside
        blocked[inside] = self.world.occupied[cy[inside], cx[inside]]
        hit = blocked.any(axis=1)
        first = blocked.argmax(axis=1)
        dist = np.where(hit, self._ray_ts[first] - self.RAY_STEP / 2, self.sensor_range)
        if self.noise_std > 0:
            dist = dist + self.np_random.normal(0.0, self.noise_std, size=dist.shape)
        return np.clip(dist, 0.0, self.sensor_range).astype(np.float32)

    def _target_vector(self) -> tuple[np.ndarray, float]:
        x, y = self.pos
        tx, ty = self.world.target_center(self.target)
        vx, vy = tx - (x + 0.5), ty - (y + 0.5)
        hx, hy = DIRECTIONS[self.orientation]
        forward, right = vx * hx + vy * hy, vx * (-hy) + vy * hx
        norm = math.hypot(forward, right)
        direction = np.array([forward / norm, right / norm] if norm > 1e-9 else [0.0, 0.0], dtype=np.float32)
        return direction, float(self.world.distance(self.target, x, y))

    def _observation(self) -> dict[str, Any]:
        self.last_rays = self._cast_rays()
        direction, distance = self._target_vector()
        return {
            "rays": self.last_rays.copy(),
            "target_direction": direction,
            "target_distance": np.array([distance], dtype=np.float32),
            "orientation": self.orientation,
            "velocity": np.array([self.last_velocity], dtype=np.float32),
            "turn": np.array([self.last_turn], dtype=np.float32),
            "battery": np.array([self.battery / self.battery_capacity], dtype=np.float32),
            "stage": self.stage,
        }

    def _info(self) -> dict[str, Any]:
        return {
            "reward_breakdown": dict(self.last_breakdown),
            "events": list(self.last_events),
            "position": self.pos,
            "orientation": ORIENTATIONS[self.orientation],
            "battery": self.battery,
            "stage": self.stage,
            "target": self.target,
            "visited": list(self.visited),
            "collisions": self.collisions,
            "path_length": self.path_length,
            "step": self.step_count,
            "success": self.success,
        }

    # ------------------------------------------------------------------ exportación y render
    def export_frame(self, include_map: bool = True) -> dict[str, Any]:
        """Estado completo para dibujar (CLI y visor). Es un dict serializable a JSON."""
        x, y = self.pos
        hx, hy = DIRECTIONS[self.orientation]
        rx, ry = -hy, hx
        rays = []
        for angle, dist in zip(self.RAY_ANGLES_DEG, self.last_rays):
            a = math.radians(angle)
            dx, dy = math.cos(a) * hx + math.sin(a) * rx, math.cos(a) * hy + math.sin(a) * ry
            rays.append(
                {
                    "angle_deg": float(angle),
                    "distance": round(float(dist), 3),
                    "hit": bool(dist < self.sensor_range - 1e-6),
                    "end": [round(x + 0.5 + dx * float(dist), 3), round(y + 0.5 + dy * float(dist), 3)],
                }
            )
        frame: dict[str, Any] = {
            "step": self.step_count,
            "robot": {
                "x": x,
                "y": y,
                "orientation": ORIENTATIONS[self.orientation],
                "heading_deg": 90 * self.orientation,
                "velocity": self.last_velocity,
                "turn": self.last_turn,
            },
            "rays": rays,
            "sensor_range": self.sensor_range,
            "beacons": [
                {"id": i + 1, "x": bx, "y": by, "visited": (i + 1) in self.visited}
                for i, (bx, by) in enumerate(self.world.beacons)
            ],
            "battery": {
                "value": round(self.battery, 3),
                "capacity": self.battery_capacity,
                "fraction": round(self.battery / self.battery_capacity, 4),
            },
            "reward": {
                "step": round(self.last_reward, 4),
                "total": round(self.total_reward, 4),
                "breakdown": {k: round(v, 4) for k, v in self.last_breakdown.items()},
            },
            "stage": self.stage,
            "target": self.target,
            "visited": list(self.visited),
            "collisions": self.collisions,
            "path_length": self.path_length,
            "events": list(self.last_events),
            "terminated": self.terminated,
            "truncated": self.truncated,
            "success": self.success,
        }
        if include_map:
            frame["map"] = self.world.to_dict()
        return frame

    def render_ansi(self) -> str:
        """Grilla en texto plano: # obstáculo, X pasillo bloqueado, B base, 1/2 balizas
        ('*' si ya se visitó), ^ > v < robot."""
        w = self.world
        rows = []
        for y in range(w.size):
            row = []
            for x in range(w.size):
                if (x, y) == self.pos:
                    ch = "^>v<"[self.orientation]
                elif (x, y) in w.beacons:
                    i = w.beacons.index((x, y)) + 1
                    ch = "*" if i in self.visited else str(i)
                elif w.occupied[y, x]:
                    blocked = w.incident == "blocked_corridor" and w.blocked_corridor.contains(x, y)
                    ch = "X" if blocked else "#"
                elif w.base.contains(x, y):
                    ch = "B"
                else:
                    ch = "."
                row.append(ch)
            rows.append(" ".join(row))
        border = "+" + "-" * (2 * w.size + 1) + "+"
        header = (
            f"paso {self.step_count}  batería {self.battery:.1f}/{self.battery_capacity:.0f}  "
            f"objetivo {self.target}  recompensa {self.total_reward:+.2f}"
        )
        return "\n".join([header, border, *(f"| {r} |" for r in rows), border])
