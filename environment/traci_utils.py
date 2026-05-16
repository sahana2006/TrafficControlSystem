"""TraCI helper wrappers for version-stable access."""
from __future__ import annotations

import traci


def next_tls(veh_id: str) -> tuple[str, float, str] | None:
    """
    Return (tls_id, distance, state) for the nearest upcoming TLS, or None.
    getNextTLS returns [(tlsID, tlsIndex, distance, state), ...].
    """
    try:
        upcoming = traci.vehicle.getNextTLS(veh_id)
        if not upcoming:
            return None
        tls_id, _idx, dist, state = upcoming[0]
        return tls_id, dist, state
    except traci.TraCIException:
        return None
