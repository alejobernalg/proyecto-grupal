# ROBOT EXPEDITION

Ambiente de aprendizaje por refuerzo para el laboratorio de MLOps (Guía de diseño 03).

> Un robot debe visitar dos balizas **en orden** (1 y luego 2) y volver a la base
> antes de agotar la batería, en una sala plana con paredes y obstáculos rectangulares.

**Principio de arquitectura: física ≠ decoración.** El ambiente en Python (Gymnasium)
es la única fuente de verdad: colisiones, batería, reglas y recompensas viven ahí.
El visor three.js y la vista del CLI solo dibujan el estado que exporta el simulador.

## Estructura

```
robot-expedition/
  configs/                 YAML de parámetros por experimento
  src/robot_expedition/
    envs/                  ambiente Gymnasium + wrappers
    agents/                Q-learning tabular
    cli/                   aplicación de terminal (robot-exp)
    export/                exportar estados/episodios a JSON
  viewer/                  visor three.js (Vite)
  data/                    episodios y logs (ignorado salvo data/examples/)
  models/                  Q-tables guardadas
  tests/                   pytest
```

## Instalación

Requiere Python 3.11 o superior (probado con 3.12). Python 3.10.0 no sirve: tiene un
bug de `typing` que rompe la importación de Gymnasium.

```bash
cd robot-expedition
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Ambiente (Fase 1)

```python
import gymnasium as gym
import robot_expedition.envs  # registra RobotExpedition-v0

env = gym.make("RobotExpedition-v0", config="configs/experimento_1.yaml")
obs, info = env.reset(seed=0)
obs, reward, terminated, truncated, info = env.step(0)
info["reward_breakdown"]   # desglose por componente
env.unwrapped.export_frame()  # estado completo en JSON para el visor/CLI
```

Mapa del experimento 1 (12 × 12 m; `#` obstáculo, `X` pasillo que cierra el incidente,
`B` base, `^` robot):

```
. . . . . . # # . . . .
. . . . . . # # . . 1 .
. . # # . . # # . . . .
. . # # . . # # . . . .
. . . . . . . . . . . .
. . . . . . . . . . . .
# # # # . . . # # # X X
. . . . . . . . . . . .
. . . . . . . . . . . .
. . . . # # . . . . 2 .
B ^ B . # # . . . . . .
B B B . # # . . . . . .
```

- **Acciones** `Discrete(5)`: 0 avanzar, 1 girar izquierda, 2 girar derecha, 3 retroceder, 4 quedarse.
- **Observación** `Dict`: 9 rayos (−90° a +90°, con ruido), dirección (frente, derecha) y
  distancia BFS al objetivo, orientación, velocidad y giro del último paso, batería
  normalizada y etapa. Detalle en el docstring de
  [`robot_expedition_env.py`](src/robot_expedition/envs/robot_expedition_env.py).
- **Recompensa**: shaping por potencial con Φ = −(distancia BFS al objetivo actual + tramos
  restantes), bono de baliza solo la primera vez y en orden, bono de retorno, y penalizaciones
  de tiempo, batería, colisión y batería agotada. Una config con γ < 1 que permita farmear
  quedándose quieto se rechaza al crear el ambiente.
- **`DiscreteStateWrapper`**: (x, y, orientación, etapa, batería en k niveles) →
  12·12·4·3·4 = **6 912 estados × 5 acciones = 34 560 valores Q** en el experimento 1.
- **Incidente**: `incident: blocked_corridor` cierra el pasillo este; la ruta pasa de 37 a 45 m.
- **Mapas aleatorios**: `map.seed: <entero>` genera un mapa válido (mismas reglas de separación
  y ruta base → 1 → 2 → base comprobada con BFS).
- **Episodios**: `EpisodeRecorder` guarda la lista de frames en `data/episodes/*.json`.
  Hay ejemplos del controlador de referencia en `data/examples/`.

Cinco transiciones manuales (observación → acción → física → recompensa → nueva observación):

```bash
python -m robot_expedition.demo
pytest -s tests/test_five_transitions.py
```

## CLI

```bash
robot-exp --help
robot-exp version
```

Comandos previstos (se agregan por fases):

| Comando | Fase | Qué hace |
|---|---|---|
| `robot-exp play --config configs/experimento_1.yaml` | 3 | Control manual (W/A/S/D, espacio, Q) |
| `robot-exp replay data/episodes/<archivo>.json` | 3 | Reproduce un episodio en la terminal |
| `robot-exp validate-config <yaml>` | 3 | Valida parámetros y rangos |
| `robot-exp train --config ...` | 4 | Entrena Q-learning |
| `robot-exp watch --model models/<archivo>` | 4 | Muestra el agente entrenado |
| `robot-exp evaluate` | 4 | Métricas con y sin incidente |

## Visor three.js

Se construye en la Fase 2. Uso previsto:

```bash
cd viewer
npm install
npm run dev     # abre http://localhost:5173 y carga un episodio JSON
```

## Flujo de trabajo

- Rama de trabajo: `experimento-1`.
- Commits pequeños por fase; tag `exp1-v0.1` al cerrar.
- Cada corrida se guarda en `data/runs/<fecha>_<exp>/` con config, hash del commit,
  métricas y episodios.
