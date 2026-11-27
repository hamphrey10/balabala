"""Config load + validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from quant_deriv_ai.config.settings import load_config, validate_trading_mode
from quant_deriv_ai.core.exceptions import ConfigError, TradingModeError
from quant_deriv_ai.core.models import TradingMode


def test_load_default_config() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "config" / "default.yaml")
    assert cfg.app.name == "quant-deriv-ai"
    assert cfg.trading.mode is TradingMode.DEMO
    assert cfg.trading.allow_live is False
    assert cfg.risk.martingale_forbidden is True
    assert cfg.data.root == "data"
    assert "M1" in cfg.data.default_timeframes
    assert cfg.data.allow_reconstruction is False
    assert cfg.technical.volume_is_synthetic is True
    assert cfg.technical.sma_fast == 20
    assert cfg.technical.sma_slow == 50
    assert cfg.quantitative.min_forward_lag == 1
    assert cfg.quantitative.edge_min_observations == 30
    assert cfg.quantitative.reports_dir == "reports"


def test_validate_trading_mode_demo() -> None:
    assert validate_trading_mode("demo") is TradingMode.DEMO


def test_validate_trading_mode_live_rejected() -> None:
    with pytest.raises(TradingModeError):
        validate_trading_mode("live")


def test_load_rejects_live_yaml(tmp_path: Path) -> None:
    path = tmp_path / "live.yaml"
    path.write_text(
        "app:\n  name: x\ntrading:\n  mode: live\n  allow_live: false\n",
        encoding="utf-8",
    )
    with pytest.raises((TradingModeError, ConfigError)):
        load_config(path)


def test_missing_config(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(tmp_path / "missing.yaml")
