"""
Build 4x4 urban grid with netgenerate (16 intersections, TLS, bidirectional multi-lane).
Run: python networks/grid_4x4/build_network.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

GRID_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = GRID_DIR.parent.parent


def _sumo_bin(name: str) -> str:
    home = os.environ.get("SUMO_HOME", "")
    if home:
        candidate = Path(home) / "bin" / (name + (".exe" if sys.platform == "win32" else ""))
        if candidate.exists():
            return str(candidate)
    return name


def build_grid() -> None:
    netgenerate = _sumo_bin("netgenerate")
    out_net = GRID_DIR / "network.net.xml"
    cmd = [
        netgenerate,
        "--grid",
        "--grid.number", "4",
        "--grid.length", "200",
        "--default.lanenumber", "2",
        "--default.speed", "13.89",
        "--tls.guess", "true",
        "--tls.guess.joining", "true",
        "--no-turnarounds", "true",
        "-o", str(out_net),
    ]
    subprocess.run(cmd, check=True, cwd=str(GRID_DIR))
    print(f"Generated {out_net.name} (4x4 grid, TLS at junctions)")

    # Copy TLS extract for reference
    import xml.etree.ElementTree as ET
    tree = ET.parse(out_net)
    tl_logics = tree.getroot().findall(".//tlLogic")
    if tl_logics:
        lines = ['<tlLogics xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">']
        for tl in tl_logics:
            lines.append(ET.tostring(tl, encoding="unicode"))
        lines.append("</tlLogics>")
        (GRID_DIR / "traffic_lights.tll.xml").write_text("\n".join(lines), encoding="utf-8")


def write_sumocfg() -> None:
    cfg = """<?xml version="1.0" encoding="UTF-8"?>
<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">
    <input>
        <net-file value="network.net.xml"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="3600"/>
        <step-length value="1"/>
    </time>
    <processing>
        <collision.action value="warn"/>
        <time-to-teleport value="300"/>
    </processing>
    <gui_only>
        <start value="true"/>
        <quit-on-end value="true"/>
    </gui_only>
</configuration>
"""
    (GRID_DIR / "config.sumocfg").write_text(cfg, encoding="utf-8")


def write_root_sumocfg() -> None:
    cfg = """<?xml version="1.0" encoding="UTF-8"?>
<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">
    <input>
        <net-file value="networks/grid_4x4/network.net.xml"/>
        <route-files value="routes/medium/routes.rou.xml,routes/emergency/routes.rou.xml"/>
        <additional-files value="routes/emergency/additional.xml"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="3600"/>
        <step-length value="1"/>
    </time>
    <processing>
        <collision.action value="warn"/>
        <time-to-teleport value="300"/>
    </processing>
    <gui_only>
        <start value="true"/>
        <quit-on-end value="true"/>
    </gui_only>
</configuration>
"""
    (PROJECT_ROOT / "simulation.sumocfg").write_text(cfg, encoding="utf-8")
    print("Wrote simulation.sumocfg (project root)")


if __name__ == "__main__":
    build_grid()
    write_sumocfg()
    write_root_sumocfg()
    # Regenerate routes for new network
    gen = PROJECT_ROOT / "networks" / "grid_4x4" / "generate_routes.py"
    if gen.exists():
        subprocess.run([sys.executable, str(gen), "--all"], check=False)
