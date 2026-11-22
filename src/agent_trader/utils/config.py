from __future__ import annotations

import os
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from .errors import ConfigError, LiveTradingNotAllowed
from .time import timeframe_to_seconds

_MODES = ("paper", "testnet", "live")
_EXCHANGES = ("binance",)
_MARKET_TYPES = ("spot", "futures")


@dataclass(frozen=True)
class AgentConfig:
    name: str
    mode: str
    loop_interval_seconds: int
    timezone: str
    log_level: str


@dataclass(frozen=True)
class ExchangeConfig:
    exchange: str
    market_type: str
    testnet: bool
    quote_asset: str
    request_timeout_seconds: int
    recv_window_ms: int


@dataclass(frozen=True)
class StrategyConfig:
    enabled: bool
    name: str
    symbol: str
    timeframe: str
    candles_lookback: int
    params: dict[str, Any]


@dataclass(frozen=True)
class RiskConfig:
    max_risk_per_trade_pct: float
    max_daily_loss_pct: float
    max_open_positions: int
    max_leverage: int
    stop_loss_required: bool
    max_consecutive_losses: int
    kill_switch_enabled: bool


@dataclass(frozen=True)
class ModelsConfig:
    provider: str
    model: str
    temperature: float
    max_tokens: int
    timeout_seconds: int
    api_key_env: str


@dataclass(frozen=True)
class Settings:
    agent: AgentConfig
    exchange: ExchangeConfig
    strategy: StrategyConfig
    risk: RiskConfig
    models: ModelsConfig


def _invalid(section: str, message: str) -> ConfigError:
    return ConfigError(f"Invalid configuration [{section}]: {message}")


def _check_keys(section: str, raw: dict[str, Any], cls: type) -> None:
    expected = {item.name for item in fields(cls)}
    unknown = sorted(set(raw) - expected)
    missing = sorted(expected - set(raw))
    if unknown:
        raise _invalid(section, f"unknown keys {unknown}")
    if missing:
        raise _invalid(section, f"missing keys {missing}")


def _get_str(section: str, raw: dict[str, Any], key: str) -> str:
    value = raw[key]
    if not isinstance(value, str):
        raise _invalid(section, f"{key} must be a string")
    return value


def _get_bool(section: str, raw: dict[str, Any], key: str) -> bool:
    value = raw[key]
    if not isinstance(value, bool):
        raise _invalid(section, f"{key} must be true or false")
    return value


def _get_int(section: str, raw: dict[str, Any], key: str, minimum: int | None = None) -> int:
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise _invalid(section, f"{key} must be an integer")
    if minimum is not None and value < minimum:
        raise _invalid(section, f"{key} must be at least {minimum}")
    return value


def _get_float(
    section: str,
    raw: dict[str, Any],
    key: str,
    low: float | None = None,
    high: float | None = None,
) -> float:
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _invalid(section, f"{key} must be a number")
    number = float(value)
    if low is not None and number <= low:
        raise _invalid(section, f"{key} must be greater than {low}")
    if high is not None and number > high:
        raise _invalid(section, f"{key} must be at most {high}")
    return number


def _get_choice(section: str, raw: dict[str, Any], key: str, allowed: tuple[str, ...]) -> str:
    value = _get_str(section, raw, key)
    if value not in allowed:
        raise _invalid(section, f"{key} must be one of {list(allowed)}")
    return value


def _get_mapping(section: str, raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw[key]
    if not isinstance(value, dict):
        raise _invalid(section, f"{key} must be a mapping")
    return dict(value)


def _parse_agent(raw: dict[str, Any]) -> AgentConfig:
    _check_keys("agent", raw, AgentConfig)
    return AgentConfig(
        name=_get_str("agent", raw, "name"),
        mode=_get_choice("agent", raw, "mode", _MODES),
        loop_interval_seconds=_get_int("agent", raw, "loop_interval_seconds"),
        timezone=_get_str("agent", raw, "timezone"),
        log_level=_get_str("agent", raw, "log_level"),
    )


def _parse_exchange(raw: dict[str, Any]) -> ExchangeConfig:
    _check_keys("exchange", raw, ExchangeConfig)
    return ExchangeConfig(
        exchange=_get_choice("exchange", raw, "exchange", _EXCHANGES),
        market_type=_get_choice("exchange", raw, "market_type", _MARKET_TYPES),
        testnet=_get_bool("exchange", raw, "testnet"),
        quote_asset=_get_str("exchange", raw, "quote_asset"),
        request_timeout_seconds=_get_int("exchange", raw, "request_timeout_seconds"),
        recv_window_ms=_get_int("exchange", raw, "recv_window_ms"),
    )


def _parse_strategy(raw: dict[str, Any]) -> StrategyConfig:
    _check_keys("strategy", raw, StrategyConfig)
    timeframe = _get_str("strategy", raw, "timeframe")
    try:
        timeframe_to_seconds(timeframe)
    except ConfigError as exc:
        raise _invalid("strategy", str(exc)) from exc
    return StrategyConfig(
        enabled=_get_bool("strategy", raw, "enabled"),
        name=_get_str("strategy", raw, "name"),
        symbol=_get_str("strategy", raw, "symbol"),
        timeframe=timeframe,
        candles_lookback=_get_int("strategy", raw, "candles_lookback"),
        params=_get_mapping("strategy", raw, "params"),
    )


def _parse_risk(raw: dict[str, Any]) -> RiskConfig:
    _check_keys("risk", raw, RiskConfig)
    return RiskConfig(
        max_risk_per_trade_pct=_get_float("risk", raw, "max_risk_per_trade_pct", low=0, high=5),
        max_daily_loss_pct=_get_float("risk", raw, "max_daily_loss_pct", low=0, high=20),
        max_open_positions=_get_int("risk", raw, "max_open_positions", minimum=1),
        max_leverage=_get_int("risk", raw, "max_leverage", minimum=1),
        stop_loss_required=_get_bool("risk", raw, "stop_loss_required"),
        max_consecutive_losses=_get_int("risk", raw, "max_consecutive_losses"),
        kill_switch_enabled=_get_bool("risk", raw, "kill_switch_enabled"),
    )


def _parse_models(raw: dict[str, Any]) -> ModelsConfig:
    _check_keys("models", raw, ModelsConfig)
    return ModelsConfig(
        provider=_get_str("models", raw, "provider"),
        model=_get_str("models", raw, "model"),
        temperature=_get_float("models", raw, "temperature"),
        max_tokens=_get_int("models", raw, "max_tokens"),
        timeout_seconds=_get_int("models", raw, "timeout_seconds"),
        api_key_env=_get_str("models", raw, "api_key_env"),
    )


def _read_yaml(config_dir: Path, filename: str) -> dict[str, Any]:
    path = config_dir / filename
    try:
        with path.open("r", encoding="utf-8") as config_file:
            values = yaml.safe_load(config_file)
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"Could not load {path}: {exc}") from exc
    if not isinstance(values, dict):
        raise ConfigError(f"{path} must contain a YAML mapping.")
    return values


def _load_dotenv(config_path: Path) -> None:
    candidates = (config_path / ".env", config_path.parent / ".env")
    dotenv_path = next((candidate for candidate in candidates if candidate.is_file()), candidates[-1])
    load_dotenv(dotenv_path=dotenv_path, override=False)


def load_settings(config_dir: str | Path = "config") -> Settings:
    """Load YAML settings and environment variables into one typed object.

    Secret values are never read from YAML. ``api_key_env`` is only the name of
    the environment variable that contains a key; its value remains in the
    environment and is not included in the returned settings object.
    """
    config_path = Path(config_dir)
    _load_dotenv(config_path)

    settings = Settings(
        agent=_parse_agent(_read_yaml(config_path, "agent.yaml")),
        exchange=_parse_exchange(_read_yaml(config_path, "exchange.yaml")),
        strategy=_parse_strategy(_read_yaml(config_path, "strategy.yaml")),
        risk=_parse_risk(_read_yaml(config_path, "risk.yaml")),
        models=_parse_models(_read_yaml(config_path, "models.yaml")),
    )

    mode = settings.agent.mode
    if mode == "testnet" and not settings.exchange.testnet:
        raise ConfigError("Testnet mode requires exchange.testnet to be true.")

    if mode == "live":
        allow_live = os.getenv("ALLOW_LIVE", "").strip().lower() == "true"
        if settings.exchange.testnet or not allow_live:
            raise LiveTradingNotAllowed(
                "Live mode requires exchange.testnet=false and ALLOW_LIVE=true."
            )

    if mode != "paper" and not (settings.models.provider.strip() and settings.models.model.strip()):
        raise ConfigError("Non-paper mode requires models.provider and models.model.")

    return settings
