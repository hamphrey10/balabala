"""Typer subcommands: ``quant deriv …`` — Deriv API DEMO connector (read-only)."""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from quant_deriv_ai.config.settings import QuantConfig, load_config
from quant_deriv_ai.core.exceptions import ConfigError, LiveAccountForbiddenError, QuantDerivError
from quant_deriv_ai.core.logging import configure_logging, get_logger
from quant_deriv_ai.execution.deriv.client import DerivClient
from quant_deriv_ai.execution.deriv.credentials import load_credentials_from_env
from quant_deriv_ai.security.guards import assert_demo_only

deriv_app = typer.Typer(help="Deriv WebSocket API DEMO connector (read-only; no orders)")
console = Console()
err_console = Console(stderr=True)
log = get_logger(__name__)

_client: DerivClient | None = None


def _get_client(cfg: QuantConfig | None = None) -> DerivClient:
    """Return process-local client; ConfigError is non-fatal when cfg omitted."""
    global _client
    if _client is None:
        timeout_s = 30.0
        if cfg is not None:
            timeout_s = cfg.deriv.timeout_s
        else:
            try:
                timeout_s = load_config().deriv.timeout_s
            except ConfigError:
                timeout_s = 30.0
        _client = DerivClient(timeout_s=timeout_s)
    return _client


@deriv_app.command("connect")
def deriv_connect() -> None:
    """Open WebSocket, authorize with API token, verify DEMO (is_virtual=1)."""
    configure_logging(level="INFO")
    try:
        cfg = load_config()
        assert_demo_only(cfg.trading.mode)
        creds = load_credentials_from_env(require_complete=True)
        assert creds is not None
        client = _get_client(cfg)
        account = client.connect(creds)
    except LiveAccountForbiddenError as exc:
        err_console.print(f"[red]LIVE lock:[/red] {exc}")
        raise typer.Exit(2) from exc
    except QuantDerivError as exc:
        err_console.print(f"[red]deriv connect failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    table = Table(title="Deriv DEMO connected")
    table.add_column("Field")
    table.add_column("Value")
    for key, value in (
        ("loginid", account.loginid),
        ("is_virtual", account.is_virtual),
        ("currency", account.currency),
        ("balance", account.balance),
        ("scopes", ",".join(account.scopes)),
    ):
        table.add_row(key, str(value))
    console.print(table)
    # Never print api_token / raw credentials.
    log.info("connect ok loginid={} is_virtual={}", account.loginid, account.is_virtual)


@deriv_app.command("status")
def deriv_status() -> None:
    """Show connector status (no secrets)."""
    configure_logging(level="INFO")
    client = _get_client()
    status = client.status()
    console.print_json(json.dumps(status.model_dump(), default=str))


@deriv_app.command("account")
def deriv_account() -> None:
    """Print DEMO account balance / currency / loginid (authorize or balance)."""
    configure_logging(level="INFO")
    cfg = load_config()
    client = _get_client(cfg)
    try:
        if client.state.value != "connected":
            creds = load_credentials_from_env(require_complete=True)
            assert creds is not None
            account = client.connect(creds)
        else:
            account = client.account_info()
    except LiveAccountForbiddenError as exc:
        err_console.print(f"[red]LIVE lock:[/red] {exc}")
        raise typer.Exit(2) from exc
    except QuantDerivError as exc:
        err_console.print(f"[red]deriv account failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print(account.model_dump_json(indent=2))


@deriv_app.command("disconnect")
def deriv_disconnect() -> None:
    """Shut down the Deriv WebSocket connection."""
    configure_logging(level="INFO")
    client = _get_client()
    client.disconnect()
    console.print("[green]deriv disconnected[/green]")
