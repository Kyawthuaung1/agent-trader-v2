from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agent_trader.utils.config import load_settings
from agent_trader.utils.errors import ConfigError, LiveTradingNotAllowed
from agent_trader.utils.time import timeframe_to_seconds

CONFIG_DIR = PROJECT_ROOT / "config"


def _copy_config(tmp_path: Path) -> Path:
    destination = tmp_path / "config"
    shutil.copytree(CONFIG_DIR, destination)
    return destination


def _update_yaml(path: Path, key: str, value: object) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data[key] = value
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_defaults_load_successfully() -> None:
    settings = load_settings(CONFIG_DIR)

    assert settings.agent.mode == "paper"
    assert settings.exchange.testnet is True
    assert settings.strategy.enabled is False
    assert settings.models.provider == ""
    assert settings.models.model == ""


def test_live_mode_without_allow_live_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = _copy_config(tmp_path)
    _update_yaml(config_dir / "agent.yaml", "mode", "live")
    _update_yaml(config_dir / "exchange.yaml", "testnet", False)
    monkeypatch.delenv("ALLOW_LIVE", raising=False)

    with pytest.raises(LiveTradingNotAllowed):
        load_settings(config_dir)


def test_testnet_mode_requires_testnet_exchange(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = _copy_config(tmp_path)
    _update_yaml(config_dir / "agent.yaml", "mode", "testnet")
    _update_yaml(config_dir / "exchange.yaml", "testnet", False)
    monkeypatch.setenv("ALLOW_LIVE", "false")

    with pytest.raises(ConfigError, match="requires exchange.testnet"):
        load_settings(config_dir)


def test_invalid_risk_values_are_rejected(tmp_path: Path) -> None:
    config_dir = _copy_config(tmp_path)
    _update_yaml(config_dir / "risk.yaml", "max_risk_per_trade_pct", 0)

    with pytest.raises(ConfigError, match="Invalid configuration"):
        load_settings(config_dir)


def test_timeframe_to_seconds_accepts_common_intervals() -> None:
    assert timeframe_to_seconds("15m") == 900
    assert timeframe_to_seconds("1h") == 3_600
    assert timeframe_to_seconds("4h") == 14_400
    assert timeframe_to_seconds("1d") == 86_400

    with pytest.raises(ConfigError):
        timeframe_to_seconds("0m")
