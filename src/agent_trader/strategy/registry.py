from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from ..utils.errors import ConfigError
from .base import Strategy

_StrategyType = TypeVar("_StrategyType", bound=type[Strategy])
_REGISTRY: dict[str, type[Strategy]] = {}


def register(name: str) -> Callable[[_StrategyType], _StrategyType]:
    """Register a Strategy subclass under a stable name."""
    if not isinstance(name, str) or not name.strip():
        raise ConfigError("Strategy name must be a non-empty string.")
    key = name.strip()

    def decorator(strategy_class: _StrategyType) -> _StrategyType:
        if not isinstance(strategy_class, type) or not issubclass(strategy_class, Strategy):
            raise ConfigError("Only Strategy subclasses can be registered.")
        if key in _REGISTRY and _REGISTRY[key] is not strategy_class:
            raise ConfigError(f"A strategy named {key!r} is already registered.")
        strategy_class.name = key
        _REGISTRY[key] = strategy_class
        return strategy_class

    return decorator


def get_strategy(name: str, params: dict) -> Strategy:
    """Instantiate a registered strategy or raise ConfigError if unknown."""
    try:
        strategy_class = _REGISTRY[name]
    except (KeyError, TypeError) as exc:
        raise ConfigError(f"Unknown strategy: {name!r}.") from exc
    return strategy_class(params)


def list_strategies() -> list[str]:
    """Return registered strategy names in deterministic order."""
    return sorted(_REGISTRY)
