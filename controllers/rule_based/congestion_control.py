"""
Congestion monitoring and green extension.
ICP = sum(Q_i) / L
"""
from __future__ import annotations

import config
from environment.action_handler import ActionHandler, SignalAction
from environment.state_extractor import IntersectionState, StateExtractor


class CongestionController:
    def __init__(self, action_handler: ActionHandler, state_extractor: StateExtractor) -> None:
        self.actions = action_handler
        self.state = state_extractor

    def congested_intersections(
        self, intersections: dict[str, IntersectionState]
    ) -> list[str]:
        return [
            tls_id
            for tls_id, ist in intersections.items()
            if ist.queue_length > config.CONGESTION_QUEUE_LIMIT
        ]

    def extend_green(self, tls_id: str) -> None:
        self.actions.apply(tls_id, SignalAction.EXTEND)

    def intersection_congestion_pressure(self, intersections: dict[str, IntersectionState]) -> float:
        """ICP = sum(Q_i) / L"""
        if not intersections:
            return 0.0
        total_q = sum(ist.queue_length for ist in intersections.values())
        L = config.DEFAULT_LANE_LENGTH_M * len(intersections)
        return total_q / max(L, 1.0)
