"""CLI tests for ``quant data`` (offline commands; download needs MT5)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from quant_deriv_ai.cli.app import app
from quant_deriv_ai.config.settings import DataSettings, QuantConfig, load_config
from quant_deriv_ai.market_data.engine import MarketDataEngine
from quant_deriv_ai.market_data.models import SeriesKind
from quant_deriv_ai.market_data.normalize import normalize_frame

runner = CliRunner()


def _seed(data_root: Path) -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    rows = []
    for i in range(10):
        c = 1.0 + i * 0.01
        rows.append(
            {
                "symbol": "EURUSD",
                "timeframe": "M1",
                "time": start + timedelta(minutes=i),
                "open": c,
                "high": c + 0.01,
                "low": c - 0.01,
                "close": c,
                "tick_volume": 1,
                "spread": 1,
                "real_volume": 0,
                "is_reconstructed": False,
                "reconstruction_method": "none",
            }
        )
    frame = normalize_frame(pd.DataFrame(rows), SeriesKind.CANDLES)
    engine = MarketDataEngine.from_root(
        data_root, settings=DataSettings(freshness_max_age_s=31_536_000)
    )
    engine.store.write_working(
        frame, symbol="EURUSD", kind=SeriesKind.CANDLES, timeframe="M1"
    )


def test_data_help() -> None:
    result = runner.invoke(app, ["data", "--help"])
    assert result.exit_code == 0
    for cmd in ("download", "update", "validate", "inspect", "stats"):
        assert cmd in result.stdout


def test_data_stats_inspect_validate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "data"
    _seed(data_root)

    def _load(path: Path | str | None = None) -> QuantConfig:
        cfg = load_config(path)
        return cfg.model_copy(
            update={"data": cfg.data.model_copy(update={"root": str(data_root)})}
        )

    monkeypatch.setattr("quant_deriv_ai.cli.data_cmds.load_config", _load)

    stats = runner.invoke(app, ["data", "stats", "-s", "EURUSD"])
    assert stats.exit_code == 0
    assert "EURUSD" in stats.stdout
    assert "M1" in stats.stdout

    inspect = runner.invoke(
        app, ["data", "inspect", "-s", "EURUSD", "-k", "candles", "-t", "M1"]
    )
    assert inspect.exit_code == 0
    assert "EURUSD" in inspect.stdout

    validate = runner.invoke(
        app, ["data", "validate", "-s", "EURUSD", "-k", "candles", "-t", "M1"]
    )
    # Default is historical mode — freshness is informational, exit 0 when otherwise ok.
    assert validate.exit_code == 0
    assert "row_count" in validate.stdout
