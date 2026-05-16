"""
SUMO + TraCI simulation environment.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Callable, Protocol

import traci

import config
from environment.action_handler import ActionHandler
from environment.ev_tracker import EVTracker
from environment.gui_tracker import GuiTracker
from environment.live_logger import LiveLogger
from environment.state_extractor import StateExtractor


class BaseController(Protocol):
    def reset(self) -> None: ...
    def step(self, state: dict[str, Any]) -> None: ...
    def on_simulation_end(self) -> dict[str, Any]: ...


class SumoEnvironment:
    def __init__(
        self,
        use_gui: bool | None = None,
        traffic_profile: str | None = None,
        controller: BaseController | None = None,
        step_callback: Callable[[dict[str, Any]], None] | None = None,
        live_logger: LiveLogger | None = None,
        metrics_collector: Any = None,
    ) -> None:
        self.use_gui = use_gui if use_gui is not None else config.USE_GUI
        self.traffic_profile = traffic_profile or config.TRAFFIC_PROFILE
        self.controller = controller
        self.step_callback = step_callback
        self.logger = live_logger or LiveLogger()
        self.metrics = metrics_collector
        self.action_handler = ActionHandler()
        self.state_extractor = StateExtractor()
        self.gui = GuiTracker() if self.use_gui else None
        self.ev_tracker = EVTracker(self.logger)
        self._running = False
        self._ev_ids: list[str] = []

    def _sumo_binary(self) -> str:
        name = "sumo-gui" if self.use_gui else "sumo"
        home = os.environ.get("SUMO_HOME") or config.SUMO_HOME
        if home:
            ext = ".exe" if sys.platform == "win32" else ""
            path = Path(home) / "bin" / f"{name}{ext}"
            if path.exists():
                return str(path)
        return name

    def _build_sumo_cmd(self) -> list[str]:
        net = config.NET_FILE
        if not net.exists():
            raise FileNotFoundError(
                f"Network not found: {net}. Run: python networks/grid_4x4/build_network.py"
            )
        civilian = config.route_file(self.traffic_profile)
        emergency = config.emergency_route_file()
        if not civilian.exists():
            raise FileNotFoundError(
                f"Routes not found: {civilian}. Run: python networks/grid_4x4/generate_routes.py"
            )
        if not emergency.exists():
            raise FileNotFoundError(f"Emergency routes missing: {emergency}")

        # Emergency routes FIRST so EV_1 + ambulance vType load before civilian traffic
        route_files = f"{emergency},{civilian}"

        cmd = [
            self._sumo_binary(),
            "-n", str(net),
            "-r", route_files,
            "--step-length", str(config.STEP_LENGTH_S),
            "--seed", str(config.RANDOM_SEED),
            "--collision.action", "warn",
            "--time-to-teleport", "300",
            "--route-steps", "1",
        ]
        if self.use_gui:
            cmd.extend([
                "--start",
                "--quit-on-end",
                "--delay", "80",
                "--gui-settings-file", self._gui_settings_path(),
            ])
        return cmd

    def _gui_settings_path(self) -> str:
        """Minimal GUI settings: show vehicle names, colored EV."""
        path = config.NETWORK_DIR / "gui-settings.xml"
        if not path.exists():
            path.write_text(
                """<viewsettings>
    <scheme name="real world">
        <vehicles vehicleMode="0" vehicleQuality="2" minSize="1.0"
                  showBlinker="1" drawMinGap="0" drawBrakeGap="0"
                  showRoute="1" showBTRange="0" constantSize="0"
                  vehicleName_show="1" vehicleName_size="60"
                  vehicleName_color="255,0,0"/>
    </scheme>
</viewsettings>
""",
                encoding="utf-8",
            )
        return str(path)

    def start(self) -> None:
        config.ensure_dirs()
        self.logger.info(
            f"Starting SUMO ({'GUI' if self.use_gui else 'headless'}) "
            f"traffic={self.traffic_profile} EV={config.EV_VEHICLE_ID} depart={config.EV_DEPART_TIME_S}s"
        )
        traci.start(self._build_sumo_cmd())
        self._running = True

        if self.gui:
            self.gui.setup_network_view()

        self.state_extractor.ev_ids = [config.EV_VEHICLE_ID]
        if self.controller:
            self.controller.reset()

        self.logger.info(
            f"Waiting for EV '{config.EV_VEHICLE_ID}' at depart={config.EV_DEPART_TIME_S}s"
        )

    def stop(self) -> None:
        if self._running:
            if self.gui:
                self.gui.stop_tracking()
            traci.close()
            self._running = False

    def step(self) -> bool:
        traci.simulationStep()
        sim_time = traci.simulation.getTime()

        self._refresh_ev_ids()
        state = self.state_extractor.full_state()

        if self.controller:
            self.controller.step(state)

        preempted: set[str] = set()
        if self.controller and hasattr(self.controller, "preemption"):
            preempted = set(self.controller.preemption.active.keys())

        if self.gui:
            self.gui.track_ev(sim_time)

        self.ev_tracker.log_continuous(sim_time, preempted)
        self.logger.log_step(sim_time, state["evs"], state["intersections"], preempted)

        if self.metrics:
            self.metrics.record_step(sim_time, state["intersections"], state["evs"], self.controller)

        if self.step_callback:
            self.step_callback(state)

        return sim_time < config.SIMULATION_END_S

    def _refresh_ev_ids(self) -> None:
        ev_id = config.EV_VEHICLE_ID
        if ev_id in traci.vehicle.getIDList() and ev_id not in self._ev_ids:
            self._ev_ids.append(ev_id)
            self.logger.info(f"[EV] Vehicle '{ev_id}' is now in the network (visible in GUI)")
            if self.gui:
                self.gui.track_ev(traci.simulation.getTime(), force=True)
        self.state_extractor.ev_ids = [ev_id] if ev_id in traci.vehicle.getIDList() else self._ev_ids

    def run(self) -> dict[str, Any]:
        self.start()
        try:
            while self.step():
                pass
        finally:
            summary = {}
            if self.controller:
                summary = self.controller.on_simulation_end()
            self.logger.info("Simulation finished.")
            self.stop()
        return summary
