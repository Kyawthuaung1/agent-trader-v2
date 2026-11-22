class AgentTraderError(Exception):
    """Base exception for errors raised by the agent-trader package."""


class ConfigError(AgentTraderError):
    """Raised when application configuration is missing or invalid."""


class ExchangeError(AgentTraderError):
    """Raised when an exchange operation fails."""


class RiskViolation(AgentTraderError):
    """Raised when a requested action violates a risk limit."""


class LiveTradingNotAllowed(AgentTraderError):
    """Raised when live trading is not explicitly enabled and safe to use."""
