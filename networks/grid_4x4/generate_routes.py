"""
Generate civilian routes via SUMO randomTrips.py.
LOW=100, MEDIUM=300, HIGH=700 vehicles over simulation horizon.
Run: python networks/grid_4x4/generate_routes.py [--all | --profile medium]
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

GRID_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = GRID_DIR.parent.parent
NET_FILE = GRID_DIR / "network.net.xml"
ROUTES_ROOT = PROJECT_ROOT / "routes"

TRAFFIC_LEVELS = {
    "low": 100,
    "medium": 300,
    "high": 700,
}
SIM_END = 3600


def _sumo_tools() -> Path:
    home = os.environ.get("SUMO_HOME", "")
    if not home:
        raise EnvironmentError("Set SUMO_HOME to your SUMO installation directory.")
    script = Path(home) / "tools" / "randomTrips.py"
    if not script.exists():
        raise FileNotFoundError(f"randomTrips.py not found at {script}")
    return script


def _inject_civilian_vtype(rou_path: Path) -> None:
    text = rou_path.read_text(encoding="utf-8")
    vtype = (
        '    <vType id="civilian" accel="2.6" decel="4.5" sigma="0.5" length="5"\n'
        '           maxSpeed="13.89" color="255,255,0" guiShape="passenger"/>\n'
    )
    if 'id="civilian"' not in text:
        text = re.sub(r"(<routes[^>]*>)", r"\1\n" + vtype, text, count=1)
    if 'type="civilian"' not in text:
        text = re.sub(
            r'(<vehicle id="[^"]+" depart="[^"]+")>',
            r'\1 type="civilian">',
            text,
        )
    rou_path.write_text(text, encoding="utf-8")


def generate_profile(profile: str, seed: int = 42) -> None:
    if not NET_FILE.exists():
        raise FileNotFoundError(f"Network missing: {NET_FILE}. Run build_network.py first.")

    n_veh = TRAFFIC_LEVELS[profile]
    period = SIM_END / n_veh
    out_dir = ROUTES_ROOT / profile
    out_dir.mkdir(parents=True, exist_ok=True)
    trips = out_dir / "trips.trips.xml"
    routes = out_dir / "routes.rou.xml"

    cmd = [
        sys.executable,
        str(_sumo_tools()),
        "-n", str(NET_FILE),
        "-o", str(trips),
        "-r", str(routes),
        "-e", str(SIM_END),
        "-p", str(period),
        "--fringe-factor", "2",
        "--validate",
        "--seed", str(seed),
        "--trip-attributes", 'type="civilian"',
    ]
    subprocess.run(cmd, check=True, cwd=str(GRID_DIR))
    _inject_civilian_vtype(routes)
    print(f"[{profile}] {n_veh} vehicles, period={period:.2f}s -> {routes}")


def write_emergency_routes() -> None:
    """Ambulance EV: red, fast, cross-town route A0 -> D3."""
    ev_dir = ROUTES_ROOT / "emergency"
    ev_dir.mkdir(parents=True, exist_ok=True)

    routes_xml = """<?xml version="1.0" encoding="UTF-8"?>
<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">
    <vType id="ambulance"
           vClass="emergency"
           accel="3.0"
           decel="4.5"
           sigma="0"
           length="5"
           maxSpeed="25"
           color="255,0,0"
           guiShape="emergency"
           speedFactor="1.1"
           impatience="1"
           lcCooperative="0"/>
    <route id="ev_route" edges="A0B0 B0C0 C0D0 D0D1 D1D2 D2D3"/>
    <vehicle id="EV_1"
             type="ambulance"
             route="ev_route"
             depart="10"
             departSpeed="max"
             departLane="best"/>
</routes>
"""
    (ev_dir / "routes.rou.xml").write_text(routes_xml, encoding="utf-8")

    additional = """<?xml version="1.0" encoding="UTF-8"?>
<additional xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/additional_file.xsd">
</additional>
"""
    (ev_dir / "additional.xml").write_text(additional, encoding="utf-8")
    print(f"Emergency route written -> {ev_dir / 'routes.rou.xml'}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--profile", choices=list(TRAFFIC_LEVELS), default="medium")
    p.add_argument("--all", action="store_true", help="Generate low, medium, high")
    args = p.parse_args()

    write_emergency_routes()
    if args.all:
        for prof in TRAFFIC_LEVELS:
            generate_profile(prof)
    else:
        generate_profile(args.profile)


if __name__ == "__main__":
    main()
