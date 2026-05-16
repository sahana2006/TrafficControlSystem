"""ICP = sum(Q_i) / L"""


def compute_icp(total_queue: float, network_length: float) -> float:
    return total_queue / max(network_length, 1.0)
