"""
Central configuration for the Emergency Vehicle Traffic Signal Control System.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
NETWORKS_DIR = PROJECT_ROOT / "networks"
ROUTES_DIR = PROJECT_ROOT / "routes"
RESULTS_DIR = PROJECT_ROOT / "results"
PLOTS_DIR = RESULTS_DIR / "plots"
METRICS_CSV = RESULTS_DIR / "metrics.csv"
LOGS_TXT = RESULTS_DIR / "logs.txt"
SIMULATION_CFG = PROJECT_ROOT / "simulation.sumocfg"

GRID_NAME = "grid_4x4"
NETWORK_DIR = NETWORKS_DIR / GRID_NAME
NET_FILE = NETWORK_DIR / "network.net.xml"
SUMOCFG_FILE = NETWORK_DIR / "config.sumocfg"

GRID_ROWS = 4
GRID_COLS = 4
INTERSECTION_SPACING_M = 200.0
LANES_PER_EDGE = 2
DEFAULT_LANE_LENGTH_M = INTERSECTION_SPACING_M

SIMULATION_END_S = 3600
STEP_LENGTH_S = 1.0
USE_GUI = False
RANDOM_SEED = 42

TRAFFIC_PROFILE = "medium"
TRAFFIC_VEHICLE_COUNTS = {"low": 100, "medium": 300, "high": 700}

# Emergency vehicle — must match routes/emergency/routes.rou.xml
EV_TYPE_ID = "ambulance"
EV_VEHICLE_ID = "EV_1"
EV_ROUTE_ID = "ev_route"
EV_DEPART_TIME_S = 10.0
EV_MAX_SPEED_MPS = 25.0
EV_DETECTION_RADIUS_M = 150.0
EV_PREEMPTION_THRESHOLD_M = 120.0
EV_CLEARANCE_DISTANCE_M = 30.0

# SUMO-GUI tracking (zoomed-out overview + EV track)
GUI_VIEW_ID = "View #0"
GUI_ZOOM = 4000.0
GUI_TRACK_INTERVAL_S = 1.0

# DQN hyperparameters
DQN_MAX_TLS = 16
DQN_HIDDEN = 128
DQN_LR = 1e-3
DQN_GAMMA = 0.99
DQN_BUFFER_SIZE = 10000
DQN_BATCH_SIZE = 64
DQN_TARGET_UPDATE = 100
DQN_EPSILON_START = 1.0
DQN_EPSILON_END = 0.05
DQN_EPSILON_DECAY = 0.9995
DQN_MODEL_PATH = RESULTS_DIR / "models" / "dqn.pt"
COMPARISON_CSV = RESULTS_DIR / "comparison_metrics.csv"

# Reward weights
DQN_REWARD_EV_SPEED = 2.0
DQN_REWARD_QUEUE = 1.5
DQN_REWARD_DELAY = 1.0
DQN_REWARD_EV_STOP = 3.0
DQN_REWARD_GWSR = 1.5

CONGESTION_QUEUE_LIMIT = 8
GREEN_EXTENSION_S = 5
MIN_GREEN_S = 8
MAX_GREEN_S = 45
YELLOW_TIME_S = 3
RECOVERY_NORMALIZE_STEPS = 30

CONTROLLER_TYPES = ("rule_based", "dqn", "ppo", "hybrid_rl")
ACTIVE_CONTROLLER = "rule_based"

METRIC_NAMES = ("EVTT", "EVSF", "GWSR", "CVDI", "TRE", "ICP", "SAS")
LOG_INTERVAL_S = 5.0
EV_LOG_INTERVAL_S = 1.0

SUMO_HOME = None


def ensure_dirs() -> None:
    for d in (RESULTS_DIR, PLOTS_DIR, NETWORK_DIR, DQN_MODEL_PATH.parent):
        d.mkdir(parents=True, exist_ok=True)


def route_file(density: str | None = None) -> Path:
    density = density or TRAFFIC_PROFILE
    return ROUTES_DIR / density / "routes.rou.xml"


def emergency_route_file() -> Path:
    return ROUTES_DIR / "emergency" / "routes.rou.xml"
