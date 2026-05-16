"""
SUMO-GUI camera: auto-track emergency vehicle and set network zoom.
"""
from __future__ import annotations

import traci

import config


class GuiTracker:
    def __init__(self, view_id: str | None = None, zoom: float | None = None) -> None:
        self.view_id = view_id or config.GUI_VIEW_ID
        self.zoom = zoom if zoom is not None else config.GUI_ZOOM
        self._tracking = False
        self._last_track_t = -999.0

    def setup_network_view(self) -> None:
        """Frame full 4x4 grid before EV departs."""
        try:
            # Grid spans roughly 0..600 m
            traci.gui.setBoundary(self.view_id, 0, 0, 650, 650)
            traci.gui.setZoom(self.view_id, self.zoom)
        except traci.TraCIException:
            pass

    def track_ev(self, sim_time: float, force: bool = False) -> None:
        if not force and sim_time - self._last_track_t < config.GUI_TRACK_INTERVAL_S:
            return
        self._last_track_t = sim_time

        ev_id = config.EV_VEHICLE_ID
        if ev_id not in traci.vehicle.getIDList():
            return

        try:
            traci.gui.trackVehicle(self.view_id, ev_id)
            traci.gui.setZoom(self.view_id, self.zoom)
            self._tracking = True
        except traci.TraCIException:
            pass

    def stop_tracking(self) -> None:
        if not self._tracking:
            return
        try:
            traci.gui.trackVehicle(self.view_id, "")
            self._tracking = False
        except traci.TraCIException:
            pass
