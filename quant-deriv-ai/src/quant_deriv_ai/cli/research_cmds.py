"""Typer subcommands: ``quant research stats|edge|report`` (no orders)."""

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
from quant_deriv_ai.quantitative.engine import QuantitativeResearchEngine
from quant_deriv_ai.quantitative.models import ResearchReport
from quant_deriv_ai.security.guards import assert_demo_only

research_app = typer.Typer(help="Quantitative research (stats lab / edge / reports; no orders)")
console = Console()
err_console = Console(stderr=True)
log = get_logger(__name__)


def _engine() -> tuple[QuantitativeResearchEngine, Path]:
    cfg = load_config()
    assert_demo_only(cfg.trading.mode)
    engine = QuantitativeResearchEngine.from_config(cfg.quantitative.model_dump())
    return engine, Path(cfg.data.root)


@research_app.command("stats")
def research_stats(
    symbol: Annotated[str, typer.Option("--symbol", "-s", help="Instrument symbol")],
    timeframe: Annotated[str, typer.Option("--timeframe", "-t", help="Candle timeframe")] = "H1",
    data_root: Annotated[
        Path | None,
        typer.Option("--data-root", help="Market-data root (default from config)"),
    ] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Print full JSON report")] = False,
) -> None:
    """Descriptive + return statistics from local working candles."""
    configure_logging(level="INFO")
    try:
        engine, default_root = _engine()
        root = data_root or default_root
        report = engine.stats_from_store(root, symbol=symbol, timeframe=timeframe)
    except QuantDerivError as exc:
        err_console.print(f"[red]research stats error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"[red]research stats failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    log.info("research stats symbol={} tf={} bars={}", symbol, timeframe, report.bar_count)
    _emit(report, json_out=json_out)


@research_app.command("edge")
def research_edge(
    symbol: Annotated[str, typer.Option("--symbol", "-s", help="Instrument symbol")],
    timeframe: Annotated[str, typer.Option("--timeframe", "-t", help="Candle timeframe")] = "H1",
    data_root: Annotated[
        Path | None,
        typer.Option("--data-root", help="Market-data root (default from config)"),
    ] = None,
    lag: Annotated[int, typer.Option("--lag", help="Forward lag (bars, min 1)")] = 1,
    horizon: Annotated[int, typer.Option("--horizon", help="Forward horizon (bars)")] = 1,
    probe: Annotated[
        list[str] | None,
        typer.Option("--probe", "-p", help="Edge probe name (repeatable)"),
    ] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Print full JSON report")] = False,
) -> None:
    """Causal edge probes vs forward returns (research only — not strategies)."""
    configure_logging(level="INFO")
    try:
        engine, default_root = _engine()
        root = data_root or default_root
        report = engine.edge_from_store(
            root,
            symbol=symbol,
            timeframe=timeframe,
            forward_lag=lag,
            forward_horizon=horizon,
            probes=probe,
        )
    except QuantDerivError as exc:
        err_console.print(f"[red]research edge error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"[red]research edge failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    log.info(
        "research edge symbol={} tf={} probes={}",
        symbol,
        timeframe,
        len(report.edge_probes),
    )
    _emit(report, json_out=json_out)


@research_app.command("report")
def research_report(
    symbol: Annotated[str, typer.Option("--symbol", "-s", help="Instrument symbol")],
    timeframe: Annotated[str, typer.Option("--timeframe", "-t", help="Candle timeframe")] = "H1",
    data_root: Annotated[
        Path | None,
        typer.Option("--data-root", help="Market-data root (default from config)"),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output path (default under reports/)"),
    ] = None,
    fmt: Annotated[
        str,
        typer.Option("--format", "-f", help="markdown|json"),
    ] = "markdown",
    lag: Annotated[int, typer.Option("--lag", help="Forward lag (bars, min 1)")] = 1,
    horizon: Annotated[int, typer.Option("--horizon", help="Forward horizon (bars)")] = 1,
    probe: Annotated[
        list[str] | None,
        typer.Option("--probe", "-p", help="Edge probe name (repeatable)"),
    ] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Also print JSON to stdout")] = False,
) -> None:
    """Write a full research report (stats + edge + causality)."""
    configure_logging(level="INFO")
    try:
        engine, default_root = _engine()
        root = data_root or default_root
        report = engine.report_from_store(
            root,
            symbol=symbol,
            timeframe=timeframe,
            forward_lag=lag,
            forward_horizon=horizon,
            probes=probe,
            output_path=output,
            fmt=fmt,
        )
    except QuantDerivError as exc:
        err_console.print(f"[red]research report error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"[red]research report failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    path = report.meta.get("report_path")
    console.print(f"[green]report written:[/green] {path}")
    log.info("research report path={}", path)
    if json_out:
        console.print_json(json.dumps(report.model_dump(mode="json"), default=str))
    else:
        _emit_summary_table(report)


def _emit(report: ResearchReport, *, json_out: bool) -> None:
    if json_out:
        console.print_json(json.dumps(report.model_dump(mode="json"), default=str))
        return
    _emit_summary_table(report)


def _emit_summary_table(report: ResearchReport) -> None:
    table = Table(title=f"ResearchReport {report.symbol} {report.timeframe}")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("as_of", str(report.as_of))
    table.add_row("bars", str(report.bar_count))
    table.add_row("summary", report.summary)
    table.add_row("no_orders", str(report.meta.get("no_orders", True)))
    if report.returns is not None:
        d = report.returns.descriptive
        table.add_row("ret_mean", _fmt(d.mean))
        table.add_row("ret_std", _fmt(d.std))
        table.add_row("ann_vol", _fmt(report.returns.annualized_vol))
        table.add_row("hit+", _fmt(report.returns.hit_rate_positive))
    console.print(table)

    if report.edge_probes:
        edge_table = Table(title="Edge probes")
        edge_table.add_column("Probe")
        edge_table.add_column("Active")
        edge_table.add_column("Hit")
        edge_table.add_column("Expectancy")
        edge_table.add_column("Sharpe")
        edge_table.add_column("Verdict")
        for e in report.edge_probes:
            edge_table.add_row(
                e.probe_name,
                str(e.active_signals),
                _fmt(e.hit_rate),
                _fmt(e.expectancy),
                _fmt(e.sharpe),
                e.verdict.value,
            )
        console.print(edge_table)

    if report.causality:
        c_table = Table(title="Causality")
        c_table.add_column("Check")
        c_table.add_column("Status")
        c_table.add_column("Detail")
        for c in report.causality:
            c_table.add_row(c.name, c.status.value, c.detail)
        console.print(c_table)


def _fmt(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.6g}"
