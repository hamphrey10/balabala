"""Integration tests against a real MT5 DEMO terminal.

If the MetaTrader5 package, terminal, or DEMO credentials are unavailable,
real-terminal tests are marked BLOCKED (skipped) — never faked as PASS.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path

import pytest

from quant_deriv_ai.execution.mt5.client import Mt5Client, import_mt5
from quant_deriv_ai.execution.mt5.credentials import load_credentials_from_env


def _real_terminal_block_reason() -> str | None:
    if platform.system() != "Windows":
        return (
            f"BLOCKED: OS={platform.system()} — official MetaTrader5 Python bridge "
            "requires Windows + local MT5 terminal"
        )
    try:
        import_mt5()
    except Exception as exc:  # noqa: BLE001
        return f"BLOCKED: MetaTrader5 package unavailable: {exc}"
    try:
        creds = load_credentials_from_env(require_complete=False)
    except Exception as exc:  # noqa: BLE001
        return f"BLOCKED: credential load error: {exc}"
    if creds is None:
        return (
            "BLOCKED: MT5_LOGIN / MT5_PASSWORD / MT5_SERVER not set "
            "(DEMO credentials required for integration)"
        )
    return None


@pytest.mark.integration
def test_real_demo_connect_account_symbols_positions() -> None:
    """Live DEMO smoke: connect → account → symbols → positions → disconnect."""
    reason = _real_terminal_block_reason()
    if reason is not None:
        pytest.skip(reason)

    creds = load_credentials_from_env(require_complete=True)
    assert creds is not None
    client = Mt5Client(credentials=creds, max_retries=2)
    try:
        account = client.connect()
        assert account.trade_mode_label == "demo"
        assert account.currency
        assert account.server
        symbols = client.list_symbols()
        assert isinstance(symbols, list)
        positions = client.positions()
        assert isinstance(positions, list)
        status = client.status()
        assert status.state.value == "connected"
        assert status.live_lock_engaged is False
    finally:
        client.disconnect()


@pytest.mark.unit
def test_env_placeholders_not_used_as_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty placeholder env must not authenticate."""
    monkeypatch.delenv("MT5_LOGIN", raising=False)
    monkeypatch.delenv("MT5_PASSWORD", raising=False)
    monkeypatch.delenv("MT5_SERVER", raising=False)
    # Isolate from any ambient cwd `.env` (same pattern as credentials unit tests).
    empty = Path("/dev/null")
    assert load_credentials_from_env(require_complete=False, env_file=empty) is None
    # Ensure we never treat blank strings as credentials.
    monkeypatch.setenv("MT5_LOGIN", "")
    monkeypatch.setenv("MT5_PASSWORD", "")
    monkeypatch.setenv("MT5_SERVER", "")
    assert load_credentials_from_env(require_complete=False, env_file=empty) is None
    assert not os.environ.get("MT5_PASSWORD")
