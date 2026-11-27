"""MT5 error helpers wrapping official ``last_error()`` results."""

from __future__ import annotations

from typing import Any

from quant_deriv_ai.core.exceptions import Mt5ConnectionError, Mt5Error


def format_last_error(mt5_module: Any) -> tuple[int | None, str]:
    """Return ``(code, message)`` from ``mt5.last_error()`` without raising."""
    try:
        err = mt5_module.last_error()
    except Exception as exc:  # noqa: BLE001 — defensive around IPC bridge
        return None, f"last_error() unavailable: {exc}"
    if err is None:
        return None, "unknown error (last_error returned None)"
    if isinstance(err, tuple) and len(err) >= 2:
        return int(err[0]), str(err[1])
    return None, str(err)


def raise_from_last_error(
    mt5_module: Any,
    *,
    action: str,
    connection: bool = False,
) -> None:
    """Raise ``Mt5Error`` / ``Mt5ConnectionError`` using the last MT5 error."""
    code, message = format_last_error(mt5_module)
    detail = f"{action} failed: {message}"
    if code is not None:
        detail = f"{action} failed [{code}]: {message}"
    exc_cls: type[Mt5Error] = Mt5ConnectionError if connection else Mt5Error
    raise exc_cls(detail, code=code)
