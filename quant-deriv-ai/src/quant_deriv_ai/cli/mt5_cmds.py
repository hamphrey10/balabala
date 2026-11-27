"""Typer subcommands: ``quant mt5 …`` — connection & read-only queries (no orders)."""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from quant_deriv_ai.config.settings import QuantConfig, load_config
from quant_deriv_ai.core.exceptions import ConfigError, LiveAccountForbiddenError, QuantDerivError
from quant_deriv_ai.core.logging import configure_logging, get_logger
from quant_deriv_ai.execution.mt5.client import Mt5Client, detect_terminal, import_mt5
from quant_deriv_ai.execution.mt5.credentials import Mt5Credentials, load_credentials_from_env
from quant_deriv_ai.security.guards import assert_demo_only

mt5_app = typer.Typer(help="MetaTrader 5 DEMO connector (read-only; no orders)")
console = Console()
err_console = Console(stderr=True)
log = get_logger(__name__)

# Process-local client for CLI session reuse within a single invocation chain.
_client: Mt5Client | None = None


def _get_client(cfg: QuantConfig | None = None) -> Mt5Client:
    """Return the process-local client, applying YAML MT5 settings on first create."""
    global _client
    if _client is None:
        settings = (cfg if cfg is not None else load_config()).mt5
        _client = Mt5Client(
            timeout_ms=settings.timeout_ms,
            max_retries=settings.max_retries,
            backoff_base_s=settings.backoff_base_s,
            heartbeat_interval_s=settings.heartbeat_interval_s,
        )
    return _client


def _resolve_credentials(cfg: QuantConfig) -> Mt5Credentials:
    """Load env/.env credentials; fill terminal_path from config when unset."""
    creds = load_credentials_from_env(require_complete=True)
    assert creds is not None
    if not creds.terminal_path and cfg.mt5.terminal_path:
        return Mt5Credentials(
            login=creds.login,
            password=creds.password,
            server=creds.server,
            terminal_path=cfg.mt5.terminal_path,
        )
    return creds


@mt5_app.command("connect")
def mt5_connect() -> None:
    """Detect terminal, initialize, authenticate DEMO account, verify account type."""
    configure_logging(level="INFO")
    try:
        cfg = load_config()
        assert_demo_only(cfg.trading.mode)
        creds = _resolve_credentials(cfg)
        client = _get_client(cfg)
        account = client.connect(creds)
    except LiveAccountForbiddenError as exc:
        err_console.print(f"[red]LIVE lock:[/red] {exc}")
        raise typer.Exit(2) from exc
    except QuantDerivError as exc:
        err_console.print(f"[red]mt5 connect failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    table = Table(title="MT5 DEMO connected")
    table.add_column("Field")
    table.add_column("Value")
    for key, value in (
        ("login", account.login),
        ("server", account.server),
        ("trade_mode", account.trade_mode_label),
        ("company", account.company),
        ("currency", account.currency),
        ("balance", account.balance),
        ("equity", account.equity),
        ("margin", account.margin),
    ):
        table.add_row(key, str(value))
    console.print(table)
    # Never print password / raw credentials.
    log.info("connect ok server={} mode={}", account.server, account.trade_mode_label)


@mt5_app.command("status")
def mt5_status() -> None:
    """Show connector / terminal status (no secrets)."""
    configure_logging(level="INFO")
    client = _get_client()
    status = client.status()
    # Also probe package importability without connecting.
    package_ok = False
    package_detail = ""
    try:
        mt5 = import_mt5()
        package_ok = True
        package_detail = getattr(mt5, "__version__", "unknown")
    except QuantDerivError as exc:
        package_detail = str(exc)

    terminal_probe = None
    if package_ok and status.state.value == "disconnected":
        try:
            path = ""
            try:
                cfg = load_config()
                path = cfg.mt5.terminal_path
            except ConfigError:
                path = ""
            mt5 = import_mt5()
            terminal_probe = detect_terminal(mt5, path=path)
            mt5.shutdown()
        except Exception as exc:  # noqa: BLE001 — status must stay informative
            package_detail = f"{package_detail}; terminal probe: {exc}"

    payload = status.model_dump()
    payload["package_importable"] = package_ok
    payload["package_version"] = package_detail if package_ok else None
    payload["package_detail"] = package_detail
    if terminal_probe is not None:
        payload["terminal_probe"] = terminal_probe.model_dump()
    console.print_json(json.dumps(payload, default=str))


@mt5_app.command("account")
def mt5_account() -> None:
    """Print DEMO account balance, equity, margin, currency, server."""
    configure_logging(level="INFO")
    cfg = load_config()
    client = _get_client(cfg)
    try:
        if client.state.value != "connected":
            account = client.connect(_resolve_credentials(cfg))
        else:
            account = client.account_info()
    except LiveAccountForbiddenError as exc:
        err_console.print(f"[red]LIVE lock:[/red] {exc}")
        raise typer.Exit(2) from exc
    except QuantDerivError as exc:
        err_console.print(f"[red]mt5 account failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print(account.model_dump_json(indent=2))


@mt5_app.command("symbols")
def mt5_symbols(
    group: str | None = typer.Option(  # noqa: UP007
        None,
        "--group",
        "-g",
        help="Optional MT5 symbols_get group filter (e.g. '*USD*')",
    ),
    limit: int = typer.Option(50, "--limit", "-n", help="Max symbols to print"),
) -> None:
    """List instruments discovered dynamically from the terminal."""
    configure_logging(level="INFO")
    cfg = load_config()
    client = _get_client(cfg)
    try:
        if client.state.value != "connected":
            client.connect(_resolve_credentials(cfg))
        names = client.list_symbols(group=group)
    except LiveAccountForbiddenError as exc:
        err_console.print(f"[red]LIVE lock:[/red] {exc}")
        raise typer.Exit(2) from exc
    except QuantDerivError as exc:
        err_console.print(f"[red]mt5 symbols failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print(f"symbols: {len(names)} (showing up to {limit})")
    for name in names[: max(limit, 0)]:
        console.print(name)


@mt5_app.command("positions")
def mt5_positions(
    symbol: str | None = typer.Option(  # noqa: UP007
        None,
        "--symbol",
        "-s",
        help="Filter by symbol",
    ),
) -> None:
    """List open positions (read-only)."""
    configure_logging(level="INFO")
    cfg = load_config()
    client = _get_client(cfg)
    try:
        if client.state.value != "connected":
            client.connect(_resolve_credentials(cfg))
        positions = client.positions(symbol=symbol)
    except LiveAccountForbiddenError as exc:
        err_console.print(f"[red]LIVE lock:[/red] {exc}")
        raise typer.Exit(2) from exc
    except QuantDerivError as exc:
        err_console.print(f"[red]mt5 positions failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    if not positions:
        console.print("positions: 0")
        return
    table = Table(title="Open positions")
    for col in ("ticket", "symbol", "type", "volume", "price_open", "price_current", "profit"):
        table.add_column(col)
    for pos in positions:
        table.add_row(
            str(pos.ticket),
            pos.symbol,
            str(pos.type),
            str(pos.volume),
            str(pos.price_open),
            str(pos.price_current),
            str(pos.profit),
        )
    console.print(table)


@mt5_app.command("disconnect")
def mt5_disconnect() -> None:
    """Shut down the MT5 connection."""
    configure_logging(level="INFO")
    client = _get_client()
    client.disconnect()
    console.print("[green]mt5 disconnected[/green]")
