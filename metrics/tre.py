"""TRE = 1 / T_recovery"""


def compute_tre(recovery_time: float | None) -> float:
    if recovery_time is None or recovery_time <= 0:
        return 0.0
    return 1.0 / recovery_time
