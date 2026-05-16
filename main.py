"""
Emergency Vehicle Traffic Signal Control — main entry point.
Supports Rule-Based, DQN, and side-by-side comparison.
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
from visualization.comparison_graphs import ComparisonPlotGenerator, append_comparison_row, load_comparison_df
from visualization.plots import PlotGenerator


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="EV Traffic Signal Control (SUMO + TraCI)")
    p.add_argument("--gui", action="store_true", help="SUMO-GUI with zoomed-out EV tracking")
    p.add_argument("--traffic", choices=["low", "medium", "high"], default=config.TRAFFIC_PROFILE)
    p.add_argument("--controller", choices=["rule_based", "dqn"], default=config.ACTIVE_CONTROLLER)
    p.add_argument("--compare", action="store_true", help="Run rule_based then DQN and compare")
    p.add_argument("--build", action="store_true", help="Build network + regenerate routes")
    p.add_argument("--end", type=int, default=config.SIMULATION_END_S, help="Simulation end (s)")
    p.add_argument("--no-plots", action="store_true", help="Skip plot generation")
    p.add_argument("--no-train", action="store_true", help="DQN inference only (no learning)")
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


def run_single(
    controller_name: str,
    args: argparse.Namespace,
) -> tuple[dict, MetricsCollector]:
    config.ACTIVE_CONTROLLER = controller_name
    config.ensure_dirs()

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
            controller_name,
            env.action_handler,
            env.state_extractor,
            metrics,
            env.logger,
            train_dqn=not args.no_train,
        )
        env.controller.reset()

    env.start = patched_start
    logger.info(f"=== Running controller: {controller_name} ===")
    summary = env.run()
    metrics.save_csv()

    serializable = {k: v for k, v in summary.items() if k not in ("timeseries", "recovery_series", "dqn_train_losses", "dqn_episode_rewards")}
    out = config.RESULTS_DIR / f"run_summary_{controller_name}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)

    append_comparison_row(summary)

    print(f"\n=== {controller_name} Metrics ===")
    for name in config.METRIC_NAMES:
        print(f"  {name}: {serializable.get(name, 'N/A')}")
    if controller_name == "dqn":
        print(f"  total_reward: {serializable.get('total_reward', summary.get('dqn_total_reward', 0))}")

    if not args.no_plots and not args.compare:
        ts = metrics.to_dataframe()
        stream = metrics.load_stream_dataframe()
        PlotGenerator().generate_required(summary, ts, stream)

    return summary, metrics


def run_simulation(args: argparse.Namespace) -> dict:
    config.TRAFFIC_PROFILE = args.traffic
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

    if args.compare:
        if config.COMPARISON_CSV.exists():
            config.COMPARISON_CSV.unlink()
        rb_summary, rb_metrics = run_single("rule_based", args)
        dqn_summary, dqn_metrics = run_single("dqn", args)

        comp_df = load_comparison_df()
        cmp_gen = ComparisonPlotGenerator()
        dqn_rewards = dqn_summary.get("dqn_episode_rewards", [])
        paths = cmp_gen.generate_all(
            comp_df,
            dqn_rewards=dqn_rewards,
            rule_ts=rb_metrics.to_dataframe(),
            dqn_ts=dqn_metrics.to_dataframe(),
        )
        print(f"\nComparison plots saved to {config.PLOTS_DIR}/")
        for p in paths:
            print(f"  - {p.name}")
        print(f"Comparison CSV: {config.COMPARISON_CSV}")
        return {"rule_based": rb_summary, "dqn": dqn_summary}

    summary, metrics = run_single(args.controller, args)
    print(f"\nMetrics CSV: {config.METRICS_CSV}")
    print(f"Live log:    {config.LOGS_TXT}")
    if not args.no_plots:
        print(f"Plots:       {config.PLOTS_DIR}/")
    return summary


def main() -> None:
    args = parse_args()
    try:
        run_simulation(args)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Install SUMO, set SUMO_HOME, then: python main.py --build")
        sys.exit(1)


if __name__ == "__main__":
    main()
