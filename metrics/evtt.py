"""EVTT = t_arrival - t_departure"""


def compute_evtt(departure: float, arrival: float) -> float:
    return max(arrival - departure, 0.0)
