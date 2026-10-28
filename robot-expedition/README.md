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
