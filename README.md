# Emergency Vehicle Traffic Signal Control System

SUMO + Python + TraCI framework for **4×4 urban intersections** with rule-based EV signal preemption. Modular design ready for **DQN / PPO / hybrid RL**.

## Features

- **4×4 grid** (16 intersections) via `netgenerate --grid --grid.number=4 --tls.guess=true`
- **Civilian traffic** from `randomTrips.py` — LOW=100, MEDIUM=300, HIGH=700 vehicles
- **Red ambulance EV** (`color="255,0,0"`) with preemption across the grid
- **Live console logs** — junction, phase, EV speed/position, queue, preemption status
- **Results** — `results/metrics.csv`, `results/logs.txt`, `results/plots/*.png`

## Quick Start

### 1. Install

```bash
pip install -r requirements.txt
```

Set `SUMO_HOME` (Windows example):

```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
$env:PATH = "$env:SUMO_HOME\bin;$env:PATH"
```

### 2. Build network + routes

```bash
python main.py --build
```

Or manually:

```bash
python networks/grid_4x4/build_network.py
python networks/grid_4x4/generate_routes.py --all
```

### 3. Run controller (headless)

```bash
python main.py
```

### 4. Run with SUMO-GUI (see red EV + moving traffic)

```bash
python main.py --gui
```

### 5. SUMO-GUI without TraCI controller

```bash
sumo-gui -c simulation.sumocfg
```

## Options

| Flag | Description |
|------|-------------|
| `--gui` | SUMO-GUI with delay |
| `--traffic low\|medium\|high` | Vehicle count profile |
| `--build` | Regenerate network + routes |
| `--end 900` | Simulation length (seconds) |
| `--log-interval 5` | Console log interval (seconds) |

## Rule-Based Logic

```
IF EV near junction     → PREEMPT
ELIF queue high         → EXTEND green
ELIF EV lane green      → HOLD
ELSE                    → normal SWITCH cycle
```

## Outputs

```
results/
├── metrics.csv          # EVTT, EVSF, GWSR, CVDI, TRE, ICP, SAS
├── logs.txt             # Live [INFO] log stream
├── metrics_timeseries.csv
└── plots/
    ├── evtt.png
    ├── queue.png
    ├── congestion.png
    ├── evsf.png
    └── gwsr.png
```

## Project Structure

```
├── networks/grid_4x4/     # network.net.xml, build_network.py, generate_routes.py
├── routes/                # low | medium | high | emergency
├── controllers/rule_based/
├── environment/           # sumo_env, state_extractor, action_handler, live_logger
├── metrics/
├── visualization/
├── simulation.sumocfg     # Root SUMO config for GUI-only runs
├── config.py
└── main.py
```

## Future RL

Implement `BaseController` in `environment/sumo_env.py` and register in `controllers/__init__.py`.

```bash
python main.py --controller dqn   # when implemented
```

## Scaling

Copy `grid_4x4` → `grid_6x6`, update `GRID_ROWS/COLS` in `config.py`, rebuild network and routes.
