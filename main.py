"""
Emergency Vehicle Traffic Signal Control — main entry point.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

import config
from controllers import get_controller
from environment.live_logger import LiveLogger
from environment.sumo_env import SumoEnvironment
from metrics.collector import MetricsCollector
from visualization.plots import PlotGenerator


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="EV Traffic Signal Control (SUMO + TraCI)")
    p.add_argument("--gui", action="store_true", help="Run with SUMO-GUI (auto-tracks red EV)")
    p.add_argument("--traffic", choices=["low", "medium", "high"], default=config.TRAFFIC_PROFILE)
    p.add_argument("--controller", choices=list(config.CONTROLLER_TYPES), default=config.ACTIVE_CONTROLLER)
    p.add_argument("--build", action="store_true", help="Build network + regenerate routes")
    p.add_argument("--end", type=int, default=config.SIMULATION_END_S, help="Simulation end (s)")
    p.add_argument("--no-plots", action="store_true", help="Skip plot generation")
    p.add_argument("--log-interval", type=float, default=config.LOG_INTERVAL_S)
    p.add_argument("--ev-log-interval", type=float, default=config.EV_LOG_INTERVAL_S)
    return p.parse_args()


def build_all() -> None:
    subprocess.run([sys.executable, str(config.NETWORK_DIR / "build_network.py")], check=True)
    subprocess.run(
        [sys.executable, str(config.NETWORK_DIR / "generate_routes.py"), "--all"],
        check=True,
    )


def update_simulation_sumocfg(traffic: str) -> None:
    """Root config for sumo-gui -c simulation.sumocfg (emergency routes first)."""
    cfg = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">
    <input>
        <net-file value="networks/grid_4x4/network.net.xml"/>
        <route-files value="routes/emergency/routes.rou.xml,routes/{traffic}/routes.rou.xml"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="{config.SIMULATION_END_S}"/>
        <step-length value="1"/>
    </time>
    <processing>
        <collision.action value="warn"/>
        <time-to-teleport value="300"/>
    </processing>
    <gui_only>
        <gui-settings-file value="networks/grid_4x4/gui-settings.xml"/>
        <start value="true"/>
        <quit-on-end value="true"/>
        <delay value="80"/>
    </gui_only>
</configuration>
"""
    config.SIMULATION_CFG.write_text(cfg, encoding="utf-8")


def run_simulation(args: argparse.Namespace) -> dict:
    config.TRAFFIC_PROFILE = args.traffic
    config.ACTIVE_CONTROLLER = args.controller
    config.USE_GUI = args.gui
    config.SIMULATION_END_S = args.end
    config.LOG_INTERVAL_S = args.log_interval
    config.EV_LOG_INTERVAL_S = args.ev_log_interval
    config.ensure_dirs()

    if args.build or not config.NET_FILE.exists():
        print("Building network and routes...")
        build_all()

    if not config.route_file(args.traffic).exists():
        subprocess.run(
            [sys.executable, str(config.NETWORK_DIR / "generate_routes.py"), "--profile", args.traffic],
            check=True,
        )

    update_simulation_sumocfg(args.traffic)

    metrics = MetricsCollector()
    logger = LiveLogger(interval_s=args.log_interval)
    env = SumoEnvironment(
        use_gui=args.gui,
        traffic_profile=args.traffic,
        live_logger=logger,
        metrics_collector=metrics,
    )
    env.ev_tracker.interval_s = args.ev_log_interval

    original_start = env.start

    def patched_start() -> None:
        original_start()
        env.controller = get_controller(
            args.controller,
            env.action_handler,
            env.state_extractor,
            metrics,
            env.logger,
        )
        env.controller.reset()

    env.start = patched_start
    summary = env.run()
    metrics.save_csv()

    serializable = {k: v for k, v in summary.items() if k not in ("timeseries", "recovery_series")}
    with open(config.RESULTS_DIR / "run_summary.json", "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)

    print("\n=== Simulation Metrics ===")
    for name in config.METRIC_NAMES:
        print(f"  {name}: {serializable.get(name, 'N/A')}")
    print(f"\nMetrics CSV (stream): {config.METRICS_CSV}")
    print(f"Live log:             {config.LOGS_TXT}")

    if not args.no_plots:
        ts = metrics.to_dataframe()
        stream = metrics.load_stream_dataframe()
        gen = PlotGenerator()
        paths = gen.generate_required(summary, ts, stream)
        print(f"\nPlots saved to {config.PLOTS_DIR}/")
        for p in paths:
            print(f"  - {p.name}")

    return summary


def main() -> None:
    args = parse_args()
    try:
        run_simulation(args)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Install SUMO and set SUMO_HOME, then: python main.py --build")
        sys.exit(1)


if __name__ == "__main__":
    main()
