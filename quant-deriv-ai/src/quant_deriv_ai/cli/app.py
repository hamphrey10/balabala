"""Typer CLI application — entry point ``quant``."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from quant_deriv_ai import __version__
from quant_deriv_ai.cli.doctor import doctor_passed, run_doctor
from quant_deriv_ai.cli.mt5_cmds import mt5_app
from quant_deriv_ai.config.settings import load_config
from quant_deriv_ai.core.exceptions import ConfigError, QuantDerivError
from quant_deriv_ai.core.logging import configure_logging, get_logger
from quant_deriv_ai.core.models import SystemStatus, TradingMode
from quant_deriv_ai.security.guards import assert_demo_only

app = typer.Typer(
    name="quant",
    help="QUANT DERIV AI — DEMO-only algorithmic trading toolkit",
    add_completion=False,
    no_args_is_help=True,
)
config_app = typer.Typer(help="Configuration commands")
app.add_typer(config_app, name="config")
app.add_typer(mt5_app, name="mt5")

console = Console()
err_console = Console(stderr=True)

_CONFIG_OPT = typer.Option(
    None,
    "--config",
    "-c",
    help="Path to YAML config (default: config/default.yaml)",
    exists=False,
)


@app.command("version")
def version_cmd() -> None:
    """Print package version."""
    console.print(__version__)


@app.command("doctor")
def doctor_cmd() -> None:
    """Check environment, dependencies, and MT5 prerequisites (no account connection)."""
    configure_logging(level="INFO")
    results = run_doctor()
    table = Table(title="quant doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    for result in results:
        status = "[green]OK[/green]" if result.ok else "[yellow]FAIL[/yellow]"
        # escape Rich markup in free-form detail text
        table.add_row(result.name, status, result.detail.replace("[", "\\["))
    console.print(table)

    mandatory_ok = doctor_passed(results)
    mt5_ok = all(r.ok for r in results if r.name.startswith("mt5:") and r.name != "mt5:account")
    if mandatory_ok and mt5_ok:
        console.print("[green]doctor: PASS[/green] (including MT5 checks)")
        raise typer.Exit(0)
    if mandatory_ok:
        console.print(
            "[yellow]doctor: PASS (core)[/yellow] — MT5 checks failed or unavailable "
            "on this host (expected on non-Windows)."
        )
        raise typer.Exit(0)
    err_console.print("[red]doctor: FAIL[/red] — mandatory environment/dependency checks failed")
    raise typer.Exit(1)


@app.command("status")
def status_cmd(config: Path | None = _CONFIG_OPT) -> None:
    """Show high-level runtime status (no broker connection)."""
    configure_logging(level="INFO")
    log = get_logger(__name__)
    try:
        cfg = load_config(config)
        assert_demo_only(cfg.trading.mode)
    except QuantDerivError as exc:
        err_console.print(f"[red]status error:[/red] {exc}")
        raise typer.Exit(1) from exc

    from quant_deriv_ai.cli.doctor import check_mt5

    mt5 = check_mt5()
    snap = SystemStatus(
        version=__version__,
        trading_mode=TradingMode.DEMO,
        environment=cfg.app.environment,
        packages_ready=True,
        mt5_importable=mt5.ok,
        mt5_notes=mt5.detail,
    )
    log.info("status version={} mode={}", snap.version, snap.trading_mode)
    console.print(snap.model_dump_json(indent=2))


@config_app.command("validate")
def config_validate_cmd(config: Path | None = _CONFIG_OPT) -> None:
    """Validate YAML configuration with Pydantic (rejects live mode)."""
    configure_logging(level="INFO")
    path = config
    try:
        cfg = load_config(path)
        assert_demo_only(cfg.trading.mode)
    except (ConfigError, QuantDerivError) as exc:
        err_console.print(f"[red]config invalid:[/red] {exc}")
        raise typer.Exit(1) from exc
    console.print(
        f"[green]config valid[/green] app={cfg.app.name} "
        f"env={cfg.app.environment} mode={cfg.trading.mode.value}"
    )


# Typer treats the decorated function as the callable app when used as console script.
# setuptools entry point: quant = quant_deriv_ai.cli.app:app
# Calling ``app()`` runs the CLI; for Typer, ``app`` is a Typer instance which is callable.


def main() -> None:
    app()


if __name__ == "__main__":
    main()
