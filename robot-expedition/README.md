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
robot-exp validate-config configs/experimento_1.yaml   # parámetros, rangos, rutas BFS y tamaño de Q-table
robot-exp play                                         # control manual con el YAML por defecto
robot-exp play --config configs/experimento_1.yaml --incident blocked_corridor
robot-exp play --keys "wwwdwww"                        # secuencia de teclas sin teclado (demos, tests)
robot-exp replay data/examples/oracle_experimento_1.json --fps 6
```

Teclas de `play`: **W** avanzar · **A/D** girar · **S** retroceder · **espacio** quedarse · **Q** salir.
La grilla muestra paredes, obstáculos, pasillo bloqueado (`XX`), balizas `1` `2` (verdes al
visitarse), base `B`, robot `▲ ▶ ▼ ◀`, estela `·` e impactos de los rayos `•`. El panel lateral
muestra batería, objetivo, etapa, colisiones y la recompensa del paso con su desglose.
Cada partida se guarda en `data/episodes/` como episodio JSON (sirve de dataset).

La vista del CLI solo dibuja frames exportados por el simulador; `replay` no ejecuta el ambiente.

| Comando | Fase | Estado |
|---|---|---|
| `robot-exp play` · `replay` · `validate-config` | 3 | listo |
| `robot-exp play --live` | 2 | listo (WebSocket al visor) |
| `robot-exp train --config ...` | 4 | Entrena Q-learning |
| `robot-exp watch --model models/<archivo>` | 4 | Muestra el agente entrenado |
| `robot-exp evaluate` | 4 | Métricas con y sin incidente |

## Experimento 2: mapa marciano grande

`configs/experimento_2.yaml` hereda de `experimento_1.yaml` y usa una sala de 24 × 24 m
con relieve de Marte: cráteres, mesetas estratificadas, campos de rocas, dunas, un
afloramiento de basalto y un contenedor. Para la física siguen siendo rectángulos
infranqueables; `kind` solo cambia cómo se dibujan. La batería (240 u) y `max_steps` (700)
crecen con el mapa. La ruta completa mide 80 m (88 m con el pasillo bloqueado).

```bash
robot-exp validate-config configs/experimento_2.yaml
robot-exp play --config configs/experimento_2.yaml --live
```

En el visor: `examples/oracle_experimento_2.json`. Alrededor de la sala hay además un volcán
en escudo, un escarpe de cañón, un módulo de aterrizaje y remolinos de polvo.

## Modelo base: Q-learning de A a B

`configs/a_to_b.yaml` hereda de `experimento_1.yaml` (`extends`) y solo cambia la misión:
ir de la salida en la base (A) a la baliza 1 (B). Los hiperparámetros (α, γ, ε, episodios)
están en la sección `agent` del YAML.

```bash
robot-exp train --config configs/a_to_b.yaml     # ~1 min; guarda checkpoints 0, 30, 150, 450, 1050, 3000
robot-exp watch --model models/a_to_b.npz        # el agente en la terminal (añade --live para el visor)
robot-exp watch --model models/a_to_b_ep00150.npz  # un checkpoint temprano: todavía no sabe llegar
robot-exp evaluate --model models/a_to_b.npz     # con y sin incidente
```

Cada entrenamiento guarda en `data/runs/<fecha>_<exp>/` la config usada, el commit (`run.json`),
las métricas por episodio (`metrics.csv`) y un episodio por checkpoint; esos episodios también
se copian a `data/episodes/` para verlos en el visor, donde el personaje camina más torpe
cuanto menos entrenado está el modelo.

Resultado del baseline (3000 episodios): llega a B sin choques en 28 m (la ruta óptima mide
18 m). Con el pasillo bloqueado falla: aprendió una sola ruta y no se adapta.

## Visor three.js (Marte)

Diorama 3D ambientado en Marte: regolito, dunas, montañas y mesetas con bruma, cráteres,
rocas, polvo en suspensión, hábitat con paneles solares junto a la base, Fobos y Deimos.
Los obstáculos son contenedores de carga (naranja), mesetas de arenisca (coral) y bloques
de basalto (gris). Todo eso es decoración: el visor solo dibuja los frames que exporta el
simulador y entre dos frames solo interpola el dibujo.

```bash
cd viewer
npm install
npm run dev     # abre http://localhost:5173 con el primer episodio de ejemplo
```

- El selector lista `data/examples/` y `data/episodes/` (tus partidas de `robot-exp play`).
  También puedes arrastrar un `.json` a la ventana o usar **Abrir…**.
- `?episode=examples/oracle_experimento_1.json&t=20&view=1` abre un episodio en un paso y vista.
- Controles: play/pausa (espacio), ←/→ paso a paso, velocidad, línea de tiempo,
  **Cambiar vista** (V: isométrica, cenital, seguimiento), **Rutas y guías** (G),
  **Modo ligero** (L: sin sombras ni bloom).

### En vivo: el visor sigue tus teclas del CLI

Con el visor corriendo (`npm run dev`), en otra terminal:

```bash
robot-exp play --live
```

El CLI abre `http://localhost:5173/?live=ws://localhost:8765` en el navegador y envía cada
frame por WebSocket. El robot 3D se mueve con cada tecla que pulses en la terminal.
Si el visor se abre a mitad de partida, recibe el episodio completo hasta ese momento.

## Flujo de trabajo

- Rama de trabajo: `experimento-1`.
- Commits pequeños por fase; tag `exp1-v0.1` al cerrar.
- Cada corrida se guarda en `data/runs/<fecha>_<exp>/` con config, hash del commit,
  métricas y episodios.
