"""Typer subcommands: ``quant analyze technical`` — TA snapshot (no orders)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from quant_deriv_ai.config.settings import load_config
from quant_deriv_ai.core.exceptions import QuantDerivError
from quant_deriv_ai.core.logging import configure_logging, get_logger
from quant_deriv_ai.security.guards import assert_demo_only
from quant_deriv_ai.technical.engine import TechnicalAnalysisEngine

analyze_app = typer.Typer(help="Market analysis (technical; no orders)")
console = Console()
err_console = Console(stderr=True)
log = get_logger(__name__)


@analyze_app.command("technical")
def analyze_technical(
    symbol: Annotated[str, typer.Option("--symbol", "-s", help="Instrument symbol")],
    timeframe: Annotated[str, typer.Option("--timeframe", "-t", help="Candle timeframe")] = "H1",
    data_root: Annotated[
        Path | None,
        typer.Option("--data-root", help="Market-data root (default from config)"),
    ] = None,
    mtf: Annotated[
        list[str] | None,
        typer.Option("--mtf", help="Extra timeframes for MTF consensus"),
    ] = None,
    indicator: Annotated[
        list[str] | None,
        typer.Option("--indicator", "-i", help="Indicator name (repeatable; default=all)"),
    ] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Print full JSON snapshot")] = False,
    volume_real: Annotated[
        bool,
        typer.Option(
            "--volume-real",
            help="Caller asserts volume is real (default: treat as synthetic)",
        ),
    ] = False,
) -> None:
    """Compute a TechnicalSnapshot from local working candle storage."""
    configure_logging(level="INFO")
    try:
        cfg = load_config()
        assert_demo_only(cfg.trading.mode)
        root = data_root or Path(cfg.data.root)
        tech = cfg.technical.model_dump()
        tech["volume_is_synthetic"] = False if volume_real else tech["volume_is_synthetic"]
        engine = TechnicalAnalysisEngine.from_config(tech)
        snap = engine.analyze_from_store(
            root,
            symbol=symbol,
            timeframe=timeframe,
            indicators=indicator,
            mtf_timeframes=mtf,
        )
    except QuantDerivError as exc:
        err_console.print(f"[red]analyze technical error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except Exception as exc:  # noqa: BLE001 — surface unexpected IO/errors to CLI
        err_console.print(f"[red]analyze technical failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    log.info(
        "technical snapshot symbol={} tf={} bars={} trend={}",
        snap.symbol,
        snap.timeframe,
        snap.bar_count,
        snap.trend.direction.value,
    )

    if json_out:
        console.print_json(json.dumps(snap.model_dump(mode="json"), default=str))
        return

    table = Table(title=f"TechnicalSnapshot {snap.symbol} {snap.timeframe}")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("as_of", str(snap.as_of))
    table.add_row("bars", str(snap.bar_count))
    table.add_row("last_close", f"{snap.last_close:.6g}" if snap.last_close is not None else "—")
    table.add_row("trend", f"{snap.trend.direction.value} (strength={snap.trend.strength:.2f})")
    table.add_row("structure", snap.structure_bias.value)
    br = snap.breakout
    table.add_row(
        "breakout",
        f"{br.side.value} level={br.level:.6g} conf={br.confirmed}",
    )
    table.add_row("swings", str(len(snap.swings)))
    table.add_row("S/R levels", str(len(snap.support_resistance)))
    table.add_row("volume", snap.volume.note)
    if snap.mtf is not None:
        table.add_row(
            "mtf",
            f"{snap.mtf.dominant_trend.value} aligned={snap.mtf.aligned} ({snap.mtf.notes})",
        )
    console.print(table)

    if snap.mtf is not None and snap.mtf.views:
        mtf_table = Table(title="MTF views")
        mtf_table.add_column("Timeframe")
        mtf_table.add_column("Trend")
        mtf_table.add_column("Structure")
        mtf_table.add_column("RSI")
        for view in snap.mtf.views:
            rsi_txt = f"{view.rsi:.2f}" if view.rsi is not None else "—"
            mtf_table.add_row(
                view.timeframe,
                view.trend.value,
                view.structure_bias.value,
                rsi_txt,
            )
        console.print(mtf_table)

    if snap.indicators:
        ind = Table(title="Indicators (latest)")
        ind.add_column("Name")
        ind.add_column("Value")
        for key in sorted(snap.indicators):
            ind.add_row(key, f"{snap.indicators[key]:.6g}")
        console.print(ind)
