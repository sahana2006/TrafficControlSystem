"""CVDI = (1 / N_OV) * sum(W_EV - W_normal) — civilian delay index."""


def compute_cvdi(waiting_times: list[float], baseline: float = 0.0) -> float:
    if not waiting_times:
        return 0.0
    n = len(waiting_times)
    return sum(max(w - baseline, 0.0) for w in waiting_times) / n
