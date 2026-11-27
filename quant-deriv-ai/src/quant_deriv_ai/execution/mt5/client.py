"""Professional MetaTrader5 connector — DEMO-only, read-only (no orders).

Uses only documented MetaTrader5 Python APIs:
``initialize``, ``login``, ``shutdown``, ``version``, ``last_error``,
``account_info``, ``terminal_info``, ``symbols_get``, ``symbol_info``,
``symbol_info_tick``, ``symbol_select``, ``copy_rates_from_pos``,
``copy_rates_range``, ``copy_ticks_from``, ``copy_ticks_range``,
``positions_get``, ``history_deals_get``.

Intentionally absent: ``order_send``, ``order_check``, ``order_calc_*``.
"""

from __future__ import annotations

import importlib
import platform
import threading
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any, TypeVar

from quant_deriv_ai.core.exceptions import (
    LiveAccountForbiddenError,
    Mt5ConnectionError,
    Mt5Error,
    Mt5NotAvailableError,
)
from quant_deriv_ai.core.logging import get_logger
from quant_deriv_ai.execution.mt5.constants import (
    ACCOUNT_TRADE_MODE_DEMO,
    COPY_TICKS_ALL,
    account_trade_mode_label,
    resolve_timeframe,
)
from quant_deriv_ai.execution.mt5.credentials import Mt5Credentials
from quant_deriv_ai.execution.mt5.errors import raise_from_last_error
from quant_deriv_ai.execution.mt5.live_lock import LiveAccountLock
from quant_deriv_ai.execution.mt5.models import (
    AccountSnapshot,
    Candle,
    ConnectionStatus,
    DealInfo,
    Mt5ConnectionState,
    PositionInfo,
    SymbolCharacteristics,
    TerminalSnapshot,
    TickData,
)

T = TypeVar("T")
log = get_logger(__name__)


def import_mt5() -> Any:
    """Import the official MetaTrader5 package or raise a clear error."""
    try:
        return importlib.import_module("MetaTrader5")
    except ImportError as exc:
        system = platform.system()
        msg = (
            f"MetaTrader5 package is not importable on OS={system}. "
            "Official wheels target Windows with a local MT5 terminal. "
            "Install optional extra [mt5] on a Windows DEMO host."
        )
        raise Mt5NotAvailableError(msg) from exc


def detect_terminal(mt5_module: Any | None = None, path: str = "") -> TerminalSnapshot | None:
    """Probe terminal presence via ``initialize`` + ``terminal_info`` (no login).

    Caller must ``shutdown`` afterward if they own the connection. This helper
    initializes briefly when ``mt5_module`` is provided without an active session.
    """
    mt5 = mt5_module or import_mt5()
    kwargs: dict[str, Any] = {}
    if path:
        kwargs["path"] = path
    if not mt5.initialize(**kwargs):
        return None
    info = mt5.terminal_info()
    if info is None:
        return None
    data = info._asdict() if hasattr(info, "_asdict") else dict(info)
    return TerminalSnapshot(
        connected=bool(data.get("connected", False)),
        name=str(data.get("name", "")),
        company=str(data.get("company", "")),
        path=str(data.get("path", path or "")),
        data_path=str(data.get("data_path", "")),
        build=int(data.get("build", 0) or 0),
        trade_allowed=bool(data.get("trade_allowed", False)),
        ping_last=int(data.get("ping_last", 0) or 0),
    )


class Mt5Client:
    """Thread-safe MT5 connector with DEMO lock, heartbeat, and reconnect."""

    def __init__(
        self,
        credentials: Mt5Credentials | None = None,
        *,
        mt5_module: Any | None = None,
        timeout_ms: int = 60_000,
        max_retries: int = 3,
        backoff_base_s: float = 0.5,
        backoff_max_s: float = 8.0,
        heartbeat_interval_s: float = 30.0,
        live_lock: LiveAccountLock | None = None,
    ) -> None:
        self._credentials = credentials
        self._mt5 = mt5_module
        self._timeout_ms = timeout_ms
        self._max_retries = max_retries
        self._backoff_base_s = backoff_base_s
        self._backoff_max_s = backoff_max_s
        self._heartbeat_interval_s = heartbeat_interval_s
        self._live_lock = live_lock or LiveAccountLock()
        self._api_lock = threading.RLock()
        self._state = Mt5ConnectionState.DISCONNECTED
        self._account: AccountSnapshot | None = None
        self._terminal: TerminalSnapshot | None = None
        self._last_error: str | None = None
        self._last_heartbeat: float | None = None
        self._heartbeat_ok: bool | None = None
        self._owns_module = mt5_module is None

    # ------------------------------------------------------------------ lifecycle

    @property
    def state(self) -> Mt5ConnectionState:
        return self._state

    @property
    def live_lock(self) -> LiveAccountLock:
        return self._live_lock

    def connect(self, credentials: Mt5Credentials | None = None) -> AccountSnapshot:
        """Initialize terminal, authenticate, verify DEMO, reject LIVE/contest."""
        self._live_lock.assert_allowed()
        creds = credentials or self._credentials
        if creds is None:
            msg = "MT5 credentials required for connect()"
            raise Mt5ConnectionError(msg)
        self._credentials = creds

        with self._api_lock:
            self._state = Mt5ConnectionState.CONNECTING
            mt5 = self._ensure_module()
            try:
                self._initialize_and_login(mt5, creds)
                account = self._fetch_account_unlocked(mt5)
                self._enforce_demo(account)
                self._terminal = self._fetch_terminal_unlocked(mt5)
                self._account = account
                self._state = Mt5ConnectionState.CONNECTED
                self._last_heartbeat = time.monotonic()
                self._heartbeat_ok = True
                self._last_error = None
                log.info(
                    "mt5 connected server={} login={} trade_mode={}",
                    account.server,
                    account.login,
                    account.trade_mode_label,
                )
                return account
            except LiveAccountForbiddenError:
                self._state = Mt5ConnectionState.BLOCKED_LIVE
                self._safe_shutdown_unlocked()
                raise
            except Exception as exc:
                self._state = Mt5ConnectionState.ERROR
                self._last_error = str(exc)
                self._safe_shutdown_unlocked()
                raise

    def disconnect(self) -> None:
        """Close the MT5 IPC connection."""
        with self._api_lock:
            self._safe_shutdown_unlocked()
            self._state = Mt5ConnectionState.DISCONNECTED
            self._account = None
            self._terminal = None
            self._heartbeat_ok = None
            log.info("mt5 disconnected")

    def status(self) -> ConnectionStatus:
        """Return connection status without exposing secrets."""
        with self._api_lock:
            terminal_connected = None
            path = None
            if self._terminal is not None:
                terminal_connected = self._terminal.connected
                path = self._terminal.path
            return ConnectionStatus(
                state=self._state,
                server=self._account.server if self._account else None,
                login=self._account.login if self._account else None,
                trade_mode_label=self._account.trade_mode_label if self._account else None,
                terminal_connected=terminal_connected,
                terminal_path=path,
                last_error=self._last_error,
                heartbeat_ok=self._heartbeat_ok,
                live_lock_engaged=self._live_lock.engaged,
            )

    # ------------------------------------------------------------------ account / terminal

    def account_info(self) -> AccountSnapshot:
        return self._call_with_retry(self._account_info_once)

    def terminal_info(self) -> TerminalSnapshot:
        return self._call_with_retry(self._terminal_info_once)

    def heartbeat(self) -> bool:
        """Ping terminal; update heartbeat flags. Returns True when healthy."""
        self._live_lock.assert_allowed()
        try:
            snap = self.terminal_info()
            ok = bool(snap.connected)
            with self._api_lock:
                self._heartbeat_ok = ok
                self._last_heartbeat = time.monotonic()
            return ok
        except Mt5Error:
            with self._api_lock:
                self._heartbeat_ok = False
                self._last_heartbeat = time.monotonic()
            raise

    # ------------------------------------------------------------------ market data

    def list_symbols(self, group: str | None = None) -> list[str]:
        """Dynamic instrument discovery via ``symbols_get``."""

        def _once() -> list[str]:
            mt5 = self._ready_module()
            raw = mt5.symbols_get(group=group) if group else mt5.symbols_get()
            if raw is None:
                raise_from_last_error(mt5, action="symbols_get")
            names: list[str] = []
            for item in raw:
                name = getattr(item, "name", None)
                if name:
                    names.append(str(name))
            return names

        return self._call_with_retry(_once)

    def symbol_info(self, symbol: str) -> SymbolCharacteristics:
        def _once() -> SymbolCharacteristics:
            mt5 = self._ready_module()
            info = mt5.symbol_info(symbol)
            if info is None:
                raise_from_last_error(mt5, action=f"symbol_info({symbol})")
            data = info._asdict() if hasattr(info, "_asdict") else dict(info)
            return SymbolCharacteristics(
                name=str(data.get("name", symbol)),
                description=str(data.get("description", "") or ""),
                path=str(data.get("path", "") or ""),
                digits=int(data.get("digits", 0) or 0),
                point=float(data.get("point", 0.0) or 0.0),
                spread=int(data.get("spread", 0) or 0),
                volume_min=float(data.get("volume_min", 0.0) or 0.0),
                volume_max=float(data.get("volume_max", 0.0) or 0.0),
                volume_step=float(data.get("volume_step", 0.0) or 0.0),
                trade_contract_size=float(data.get("trade_contract_size", 0.0) or 0.0),
                trade_tick_size=float(data.get("trade_tick_size", 0.0) or 0.0),
                trade_tick_value=float(data.get("trade_tick_value", 0.0) or 0.0),
                currency_base=str(data.get("currency_base", "") or ""),
                currency_profit=str(data.get("currency_profit", "") or ""),
                currency_margin=str(data.get("currency_margin", "") or ""),
                bid=float(data.get("bid", 0.0) or 0.0),
                ask=float(data.get("ask", 0.0) or 0.0),
                trade_mode=int(data.get("trade_mode", 0) or 0),
                visible=bool(data.get("visible", False)),
                select=bool(data.get("select", False)),
                raw={k: _json_safe(v) for k, v in data.items()},
            )

        return self._call_with_retry(_once)

    def symbol_select(self, symbol: str, enable: bool = True) -> bool:
        def _once() -> bool:
            mt5 = self._ready_module()
            ok = bool(mt5.symbol_select(symbol, enable))
            if not ok:
                raise_from_last_error(mt5, action=f"symbol_select({symbol})")
            return ok

        return self._call_with_retry(_once)

    def copy_ticks_from(
        self,
        symbol: str,
        date_from: datetime,
        count: int,
        *,
        flags: int | None = None,
    ) -> list[TickData]:
        def _once() -> list[TickData]:
            mt5 = self._ready_module()
            tick_flags = COPY_TICKS_ALL if flags is None else flags
            if hasattr(mt5, "COPY_TICKS_ALL") and flags is None:
                tick_flags = int(mt5.COPY_TICKS_ALL)
            raw = mt5.copy_ticks_from(symbol, _as_utc(date_from), count, tick_flags)
            if raw is None:
                raise_from_last_error(mt5, action=f"copy_ticks_from({symbol})")
            return [_tick_from_row(symbol, row) for row in raw]

        return self._call_with_retry(_once)

    def copy_rates_from_pos(
        self,
        symbol: str,
        timeframe: str | int,
        start_pos: int,
        count: int,
    ) -> list[Candle]:
        def _once() -> list[Candle]:
            mt5 = self._ready_module()
            tf = resolve_timeframe(timeframe, mt5)
            tf_label = timeframe if isinstance(timeframe, str) else str(timeframe)
            raw = mt5.copy_rates_from_pos(symbol, tf, start_pos, count)
            if raw is None:
                raise_from_last_error(mt5, action=f"copy_rates_from_pos({symbol})")
            return [_candle_from_row(symbol, tf_label, row) for row in raw]

        return self._call_with_retry(_once)

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: str | int,
        date_from: datetime,
        date_to: datetime,
    ) -> list[Candle]:
        def _once() -> list[Candle]:
            mt5 = self._ready_module()
            tf = resolve_timeframe(timeframe, mt5)
            tf_label = timeframe if isinstance(timeframe, str) else str(timeframe)
            raw = mt5.copy_rates_range(
                symbol,
                tf,
                _as_utc(date_from),
                _as_utc(date_to),
            )
            if raw is None:
                raise_from_last_error(mt5, action=f"copy_rates_range({symbol})")
            return [_candle_from_row(symbol, tf_label, row) for row in raw]

        return self._call_with_retry(_once)

    # ---------------------------------------------------------- positions / history (read-only)

    def positions(self, *, symbol: str | None = None) -> list[PositionInfo]:
        def _once() -> list[PositionInfo]:
            mt5 = self._ready_module()
            raw = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
            if raw is None:
                # Empty can be () ; None is error per docs
                raise_from_last_error(mt5, action="positions_get")
            return [_position_from_row(row) for row in raw]

        return self._call_with_retry(_once)

    def history_deals(
        self,
        date_from: datetime,
        date_to: datetime,
        *,
        group: str | None = None,
    ) -> list[DealInfo]:
        def _once() -> list[DealInfo]:
            mt5 = self._ready_module()
            if group:
                raw = mt5.history_deals_get(_as_utc(date_from), _as_utc(date_to), group=group)
            else:
                raw = mt5.history_deals_get(_as_utc(date_from), _as_utc(date_to))
            if raw is None:
                raise_from_last_error(mt5, action="history_deals_get")
            return [_deal_from_row(row) for row in raw]

        return self._call_with_retry(_once)

    # ------------------------------------------------------------------ internals

    def _ensure_module(self) -> Any:
        if self._mt5 is None:
            self._mt5 = import_mt5()
        return self._mt5

    def _ready_module(self) -> Any:
        self._live_lock.assert_allowed()
        self._maybe_heartbeat_gate()
        if self._state not in {
            Mt5ConnectionState.CONNECTED,
            Mt5ConnectionState.RECONNECTING,
        }:
            msg = f"MT5 not connected (state={self._state.value})"
            raise Mt5ConnectionError(msg)
        return self._ensure_module()

    def _initialize_and_login(self, mt5: Any, creds: Mt5Credentials) -> None:
        init_kwargs: dict[str, Any] = {
            "login": creds.login,
            "password": creds.password,
            "server": creds.server,
            "timeout": self._timeout_ms,
        }
        if creds.terminal_path:
            init_kwargs["path"] = creds.terminal_path

        if not mt5.initialize(**init_kwargs):
            raise_from_last_error(mt5, action="initialize", connection=True)

        # Explicit login ensures the requested DEMO account is selected.
        authorized = mt5.login(
            creds.login,
            password=creds.password,
            server=creds.server,
            timeout=self._timeout_ms,
        )
        if not authorized:
            raise_from_last_error(mt5, action="login", connection=True)

    def _enforce_demo(self, account: AccountSnapshot) -> None:
        """Reject non-DEMO accounts; engage permanent live lock on REAL/contest."""
        mt5 = self._mt5
        demo_code = ACCOUNT_TRADE_MODE_DEMO
        if mt5 is not None and hasattr(mt5, "ACCOUNT_TRADE_MODE_DEMO"):
            demo_code = int(mt5.ACCOUNT_TRADE_MODE_DEMO)
        # Normalize via official DEMO constant when the module exposes it.
        if account.trade_mode == demo_code:
            self._live_lock.evaluate_trade_mode(ACCOUNT_TRADE_MODE_DEMO, login=account.login)
            return
        self._live_lock.evaluate_trade_mode(account.trade_mode, login=account.login)

    def _fetch_account_unlocked(self, mt5: Any) -> AccountSnapshot:
        info = mt5.account_info()
        if info is None:
            raise_from_last_error(mt5, action="account_info", connection=True)
        data = info._asdict() if hasattr(info, "_asdict") else dict(info)
        trade_mode = int(data.get("trade_mode", -1))
        return AccountSnapshot(
            login=int(data.get("login", 0)),
            trade_mode=trade_mode,
            trade_mode_label=account_trade_mode_label(trade_mode),
            balance=float(data.get("balance", 0.0) or 0.0),
            equity=float(data.get("equity", 0.0) or 0.0),
            margin=float(data.get("margin", 0.0) or 0.0),
            margin_free=float(data.get("margin_free", 0.0) or 0.0),
            margin_level=float(data.get("margin_level", 0.0) or 0.0),
            profit=float(data.get("profit", 0.0) or 0.0),
            currency=str(data.get("currency", "") or ""),
            server=str(data.get("server", "") or ""),
            company=str(data.get("company", "") or ""),
            name=str(data.get("name", "") or ""),
            leverage=int(data.get("leverage", 0) or 0),
            trade_allowed=bool(data.get("trade_allowed", False)),
        )

    def _fetch_terminal_unlocked(self, mt5: Any) -> TerminalSnapshot:
        info = mt5.terminal_info()
        if info is None:
            raise_from_last_error(mt5, action="terminal_info", connection=True)
        data = info._asdict() if hasattr(info, "_asdict") else dict(info)
        return TerminalSnapshot(
            connected=bool(data.get("connected", False)),
            name=str(data.get("name", "")),
            company=str(data.get("company", "")),
            path=str(data.get("path", "")),
            data_path=str(data.get("data_path", "")),
            build=int(data.get("build", 0) or 0),
            trade_allowed=bool(data.get("trade_allowed", False)),
            ping_last=int(data.get("ping_last", 0) or 0),
        )

    def _account_info_once(self) -> AccountSnapshot:
        with self._api_lock:
            mt5 = self._ready_module()
            account = self._fetch_account_unlocked(mt5)
            self._enforce_demo(account)
            self._account = account
            return account

    def _terminal_info_once(self) -> TerminalSnapshot:
        with self._api_lock:
            mt5 = self._ready_module()
            terminal = self._fetch_terminal_unlocked(mt5)
            self._terminal = terminal
            return terminal

    def _safe_shutdown_unlocked(self) -> None:
        if self._mt5 is None:
            return
        try:
            self._mt5.shutdown()
        except Exception as exc:  # noqa: BLE001
            log.warning("mt5 shutdown raised: {}", exc)

    def _maybe_heartbeat_gate(self) -> None:
        if self._last_heartbeat is None:
            return
        if (time.monotonic() - self._last_heartbeat) < self._heartbeat_interval_s:
            return
        # Lightweight check under the same caller's retry path.
        try:
            with self._api_lock:
                if self._mt5 is None:
                    return
                info = self._mt5.terminal_info()
                ok = info is not None and bool(getattr(info, "connected", False))
                self._heartbeat_ok = ok
                self._last_heartbeat = time.monotonic()
                if not ok:
                    msg = "heartbeat failed — terminal not connected"
                    raise Mt5ConnectionError(msg)
        except Mt5ConnectionError:
            raise
        except Exception as exc:  # noqa: BLE001
            self._heartbeat_ok = False
            msg = f"heartbeat failed: {exc}"
            raise Mt5ConnectionError(msg) from exc

    def _call_with_retry(self, fn: Callable[[], T]) -> T:
        """Serialize MT5 calls; reconnect with exponential backoff on connection errors."""
        self._live_lock.assert_allowed()
        attempt = 0
        last_exc: Exception | None = None
        while attempt <= self._max_retries:
            try:
                with self._api_lock:
                    return fn()
            except LiveAccountForbiddenError:
                raise
            except Mt5ConnectionError as exc:
                last_exc = exc
                attempt += 1
                if attempt > self._max_retries:
                    break
                delay = min(self._backoff_max_s, self._backoff_base_s * (2 ** (attempt - 1)))
                log.warning(
                    "mt5 call failed (attempt {}/{}): {}; reconnecting in {:.2f}s",
                    attempt,
                    self._max_retries,
                    exc,
                    delay,
                )
                time.sleep(delay)
                try:
                    self._reconnect()
                except LiveAccountForbiddenError:
                    raise
                except Mt5ConnectionError as reconnect_exc:
                    # Transient reconnect/IPC failures must not abort the remaining
                    # retry budget — keep backing off until max_retries is exhausted.
                    last_exc = reconnect_exc
                    log.warning(
                        "mt5 reconnect failed (attempt {}/{}): {}",
                        attempt,
                        self._max_retries,
                        reconnect_exc,
                    )
            except Mt5Error:
                raise
        assert last_exc is not None
        raise last_exc

    def _reconnect(self) -> None:
        self._live_lock.assert_allowed()
        creds = self._credentials
        if creds is None:
            msg = "cannot reconnect without credentials"
            raise Mt5ConnectionError(msg)
        with self._api_lock:
            self._state = Mt5ConnectionState.RECONNECTING
            mt5 = self._ensure_module()
            self._safe_shutdown_unlocked()
            try:
                self._initialize_and_login(mt5, creds)
                account = self._fetch_account_unlocked(mt5)
                self._enforce_demo(account)
                self._terminal = self._fetch_terminal_unlocked(mt5)
                self._account = account
                self._state = Mt5ConnectionState.CONNECTED
                self._last_heartbeat = time.monotonic()
                self._heartbeat_ok = True
                self._last_error = None
                log.info("mt5 reconnected server={}", account.server)
            except LiveAccountForbiddenError:
                self._state = Mt5ConnectionState.BLOCKED_LIVE
                self._safe_shutdown_unlocked()
                raise
            except Exception as exc:
                self._state = Mt5ConnectionState.ERROR
                self._last_error = str(exc)
                self._safe_shutdown_unlocked()
                if isinstance(exc, Mt5Error):
                    raise
                msg = f"reconnect failed: {exc}"
                raise Mt5ConnectionError(msg) from exc


# --------------------------------------------------------------------------- helpers


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _time_from_epoch(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if hasattr(row, key):
        return getattr(row, key)
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except Exception:  # noqa: BLE001
        return default


def _tick_from_row(symbol: str, row: Any) -> TickData:
    return TickData(
        symbol=symbol,
        time=_time_from_epoch(_row_get(row, "time")) or datetime.now(UTC),
        bid=float(_row_get(row, "bid", 0.0) or 0.0),
        ask=float(_row_get(row, "ask", 0.0) or 0.0),
        last=float(_row_get(row, "last", 0.0) or 0.0),
        volume=float(_row_get(row, "volume", 0.0) or 0.0),
        flags=int(_row_get(row, "flags", 0) or 0),
    )


def _candle_from_row(symbol: str, timeframe: str, row: Any) -> Candle:
    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        time=_time_from_epoch(_row_get(row, "time")) or datetime.now(UTC),
        open=float(_row_get(row, "open", 0.0) or 0.0),
        high=float(_row_get(row, "high", 0.0) or 0.0),
        low=float(_row_get(row, "low", 0.0) or 0.0),
        close=float(_row_get(row, "close", 0.0) or 0.0),
        tick_volume=int(_row_get(row, "tick_volume", 0) or 0),
        spread=int(_row_get(row, "spread", 0) or 0),
        real_volume=int(_row_get(row, "real_volume", 0) or 0),
    )


def _position_from_row(row: Any) -> PositionInfo:
    return PositionInfo(
        ticket=int(_row_get(row, "ticket", 0) or 0),
        symbol=str(_row_get(row, "symbol", "") or ""),
        type=int(_row_get(row, "type", 0) or 0),
        volume=float(_row_get(row, "volume", 0.0) or 0.0),
        price_open=float(_row_get(row, "price_open", 0.0) or 0.0),
        price_current=float(_row_get(row, "price_current", 0.0) or 0.0),
        sl=float(_row_get(row, "sl", 0.0) or 0.0),
        tp=float(_row_get(row, "tp", 0.0) or 0.0),
        profit=float(_row_get(row, "profit", 0.0) or 0.0),
        swap=float(_row_get(row, "swap", 0.0) or 0.0),
        time=_time_from_epoch(_row_get(row, "time")),
        magic=int(_row_get(row, "magic", 0) or 0),
        comment=str(_row_get(row, "comment", "") or ""),
        identifier=int(_row_get(row, "identifier", 0) or 0),
    )


def _deal_from_row(row: Any) -> DealInfo:
    return DealInfo(
        ticket=int(_row_get(row, "ticket", 0) or 0),
        order=int(_row_get(row, "order", 0) or 0),
        position_id=int(_row_get(row, "position_id", 0) or 0),
        symbol=str(_row_get(row, "symbol", "") or ""),
        type=int(_row_get(row, "type", 0) or 0),
        entry=int(_row_get(row, "entry", 0) or 0),
        volume=float(_row_get(row, "volume", 0.0) or 0.0),
        price=float(_row_get(row, "price", 0.0) or 0.0),
        profit=float(_row_get(row, "profit", 0.0) or 0.0),
        commission=float(_row_get(row, "commission", 0.0) or 0.0),
        swap=float(_row_get(row, "swap", 0.0) or 0.0),
        time=_time_from_epoch(_row_get(row, "time")),
        magic=int(_row_get(row, "magic", 0) or 0),
        comment=str(_row_get(row, "comment", "") or ""),
    )


def ensure_no_order_apis(methods: Sequence[str]) -> None:
    """Dev helper / test hook: assert order APIs are not exposed on Mt5Client."""
    forbidden = {"order_send", "order_check", "order_calc_margin", "order_calc_profit"}
    overlap = forbidden.intersection(methods)
    if overlap:
        msg = f"forbidden order APIs exposed: {sorted(overlap)}"
        raise Mt5Error(msg)
