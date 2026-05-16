"""GWSR = N_green / N_total"""


def compute_gwsr(n_green: int, n_total: int) -> float:
    if n_total == 0:
        return 0.0
    return n_green / n_total
