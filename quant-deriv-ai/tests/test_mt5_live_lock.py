"""Unit tests for the strict LIVE account lock."""

from __future__ import annotations

import pytest

from quant_deriv_ai.core.exceptions import LiveAccountForbiddenError
from quant_deriv_ai.execution.mt5.constants import (
    ACCOUNT_TRADE_MODE_CONTEST,
    ACCOUNT_TRADE_MODE_DEMO,
    ACCOUNT_TRADE_MODE_REAL,
)
from quant_deriv_ai.execution.mt5.live_lock import LiveAccountLock


def test_demo_allowed() -> None:
    lock = LiveAccountLock()
    lock.evaluate_trade_mode(ACCOUNT_TRADE_MODE_DEMO, login=1)
    lock.assert_allowed()
    assert lock.engaged is False


def test_real_engages_permanent_lock() -> None:
    lock = LiveAccountLock()
    with pytest.raises(LiveAccountForbiddenError, match="non-DEMO"):
        lock.evaluate_trade_mode(ACCOUNT_TRADE_MODE_REAL, login=99)
    assert lock.engaged is True
    with pytest.raises(LiveAccountForbiddenError):
        lock.assert_allowed()


def test_contest_also_blocked() -> None:
    lock = LiveAccountLock()
    with pytest.raises(LiveAccountForbiddenError, match="contest"):
        lock.evaluate_trade_mode(ACCOUNT_TRADE_MODE_CONTEST, login=2)
    assert lock.engaged is True
