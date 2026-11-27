"""Integration tests against a real MT5 DEMO terminal.

BLOCKED on hosts without Windows + MetaTrader5 + DEMO credentials.
"""

from __future__ import annotations

import os
import platform
from datetime import UTC, datetime, timedelta

import pytest

from quant_deriv_ai.core.exceptions import Mt5NotAvailableError
from quant_deriv_ai.execution.mt5.client import Mt5Client, import_mt5
from quant_deriv_ai.execution.mt5.credentials import load_credentials_from_env
from quant_deriv_ai.market_data.engine import MarketDataEngine

pytestmark = pytest.mark.integration


def _blocked_reason() -> str | None:
    if platform.system() != "Windows":
        return (
            f"BLOCKED: OS={platform.system()} — official MetaTrader5 Python bridge "
            "requires Windows + local MT5 terminal"
        )
    try:
        import_mt5()
    except Mt5NotAvailableError as exc:
        return f"BLOCKED: {exc}"
    if not all(os.environ.get(k) for k in ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER")):
        return "BLOCKED: MT5_* DEMO credentials not configured"
    return None


@pytest.fixture
def require_mt5_demo() -> None:
    reason = _blocked_reason()
    if reason:
        pytest.skip(reason)


def test_real_demo_market_data_download(require_mt5_demo: None, tmp_path: object) -> None:
    """Live DEMO download — skipped/BLOCKED when terminal unavailable."""
    from pathlib import Path

    creds = load_credentials_from_env(require_complete=True)
    assert creds is not None
    client = Mt5Client(credentials=creds)
    client.connect()
    try:
        symbols = client.list_symbols()
        assert symbols, "DEMO account returned no symbols"
        symbol = symbols[0]
        engine = MarketDataEngine.from_root(Path(str(tmp_path)) / "data", source=client)
        end = datetime.now(UTC)
        start = end - timedelta(hours=2)
        result = engine.download_candles(symbol, "M1", start, end)
        assert result.rows_written >= 0
    finally:
        client.disconnect()
