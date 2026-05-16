"""SAS = adaptive_actions / total_decisions"""


def compute_sas(adaptive_actions: int, total_decisions: int) -> float:
    if total_decisions == 0:
        return 0.0
    return adaptive_actions / total_decisions
