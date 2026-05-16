from controllers.rule_based.signal_logic import RuleBasedController

__all__ = ["RuleBasedController"]


def get_controller(name: str, env_action_handler, state_extractor, metrics_collector, live_logger=None):
    """Factory for controllers — extend for DQN / PPO / hybrid."""
    if name == "rule_based":
        from controllers.rule_based.signal_logic import RuleBasedController
        return RuleBasedController(
            env_action_handler, state_extractor, metrics_collector, live_logger
        )
    raise NotImplementedError(f"Controller '{name}' not implemented yet.")
