from controllers.rule_based.signal_logic import RuleBasedController

__all__ = ["RuleBasedController", "get_controller"]


def get_controller(
    name: str,
    env_action_handler,
    state_extractor,
    metrics_collector,
    live_logger=None,
    train_dqn: bool = True,
):
    """Factory for rule-based, DQN, and future RL controllers."""
    if name == "rule_based":
        from controllers.rule_based.signal_logic import RuleBasedController
        return RuleBasedController(
            env_action_handler, state_extractor, metrics_collector, live_logger
        )
    if name == "dqn":
        from controllers.dqn.dqn_controller import DQNController
        return DQNController(
            env_action_handler,
            state_extractor,
            metrics_collector,
            live_logger,
            train=train_dqn,
        )
    raise NotImplementedError(f"Controller '{name}' not implemented yet.")
