"""Typer subcommands: ``quant data …`` — market-data download/update/validate/inspect/stats."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from quant_deriv_ai.config.settings import load_config
from quant_deriv_ai.core.exceptions import QuantDerivError
from quant_deriv_ai.core.logging import configure_logging, get_logger
from quant_deriv_ai.execution.mt5.client import Mt5Client
from quant_deriv_ai.execution.mt5.credentials import load_credentials_from_env
from quant_deriv_ai.market_data.engine import MarketDataEngine
from quant_deriv_ai.market_data.models import ReconstructionMethod, SeriesKind
from quant_deriv_ai.market_data.timeframes import AVAILABLE_TIMEFRAMES
from quant_deriv_ai.security.guards import assert_demo_only

data_app = typer.Typer(help="Market data engine (DEMO MT5; no orders)")
console = Console()
err_console = Console(stderr=True)
log = get_logger(__name__)

_TF_HELP = "Candle timeframe(s). Available: " + ", ".join(AVAILABLE_TIMEFRAMES)
SymbolOpt = Annotated[list[str], typer.Option("--symbol", "-s", help="Instrument symbol(s)")]
TimeframeOpt = Annotated[list[str] | None, typer.Option("--timeframe", "-t", help=_TF_HELP)]


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _engine(connect_mt5: bool) -> MarketDataEngine:
    cfg = load_config()
    assert_demo_only(cfg.trading.mode)
    root = Path(cfg.data.root)
    source = None
    if connect_mt5:
        creds = load_credentials_from_env(require_complete=True)
        client = Mt5Client(credentials=creds)
        client.connect()
        source = client
    return MarketDataEngine.from_root(root, source=source, settings=cfg.data)


@data_app.command("download")
def data_download(
    symbol: SymbolOpt,
    timeframe: TimeframeOpt = None,
    date_from: Annotated[str, typer.Option("--from", help="UTC start (ISO-8601)")] = ...,  # type: ignore[assignment]
    date_to: Annotated[str | None, typer.Option("--to", help="UTC end (ISO-8601)")] = None,
    ticks: Annotated[bool, typer.Option("--ticks", help="Also download ticks")] = False,
    candles_only: Annotated[
        bool, typer.Option("--candles-only", help="Candles only (default)")
    ] = False,
    pin: Annotated[
        str | None,
        typer.Option("--pin", help="Pin immutable version id after download (empty = auto)"),
    ] = None,
    reconstruct: Annotated[
        str,
        typer.Option("--reconstruct", help="none|forward_fill|mark_gap (default none)"),
    ] = "none",
) -> None:
    """Download historical candles (and optional ticks) into local storage."""
    configure_logging(level="INFO")
    _ = candles_only  # default behaviour; kept for explicit CLI clarity
    try:
        method = ReconstructionMethod(reconstruct)
        engine = _engine(connect_mt5=True)
        start = _parse_dt(date_from)
        end = _parse_dt(date_to)
        assert start is not None
        tfs = timeframe or list(engine.settings.default_timeframes)
        pin_version = None if pin is None else pin
        results = []
        for sym in symbol:
            for tf in tfs:
                results.append(
                    engine.download_candles(
                        sym,
                        tf,
                        start,
                        end,
                        pin_version=pin_version,
                        reconstruct=method,
                    )
                )
            if ticks:
                results.append(
                    engine.download_ticks(sym, start, end, pin_version=pin_version)
                )
    except QuantDerivError as exc:
        err_console.print(f"[red]data download failed:[/red] {exc}")
        raise typer.Exit(1) from exc
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"[red]data download failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    table = Table(title="download results")
    table.add_column("symbol")
    table.add_column("kind")
    table.add_column("tf")
    table.add_column("fetched")
    table.add_column("written")
    table.add_column("version")
    for r in results:
        table.add_row(
            r.symbol,
            r.kind.value,
            r.timeframe or "-",
            str(r.rows_fetched),
            str(r.rows_written),
            r.version or "-",
        )
    console.print(table)


@data_app.command("update")
def data_update(
    symbol: SymbolOpt,
    timeframe: TimeframeOpt = None,
    ticks: Annotated[bool, typer.Option("--ticks", help="Incremental tick update")] = False,
) -> None:
    """Incremental update from last stored timestamp."""
    configure_logging(level="INFO")
    try:
        engine = _engine(connect_mt5=True)
        tfs = timeframe or list(engine.settings.default_timeframes)
        rows: list[Any] = []
        for sym in symbol:
            for tf in tfs:
                rows.append(engine.update_candles(sym, tf))
            if ticks:
                rows.append(engine.update_ticks(sym))
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"[red]data update failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    table = Table(title="update results")
    table.add_column("symbol")
    table.add_column("kind")
    table.add_column("tf")
    table.add_column("added")
    for r in rows:
        table.add_row(r.symbol, r.kind.value, r.timeframe or "-", str(r.rows_added))
    console.print(table)


@data_app.command("validate")
def data_validate(
    symbol: Annotated[str, typer.Option("--symbol", "-s")] = ...,  # type: ignore[assignment]
    kind: Annotated[str, typer.Option("--kind", "-k", help="candles|ticks")] = "candles",
    timeframe: Annotated[str | None, typer.Option("--timeframe", "-t")] = None,
) -> None:
    """Run data-quality checks on a stored series (no fabrication)."""
    configure_logging(level="INFO")
    try:
        engine = _engine(connect_mt5=False)
        report = engine.validate(symbol, SeriesKind(kind), timeframe=timeframe)
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"[red]data validate failed:[/red] {exc}")
        raise typer.Exit(1) from exc
    console.print_json(json.dumps(report.model_dump(mode="json"), default=str))
    raise typer.Exit(0 if report.ok else 2)


@data_app.command("inspect")
def data_inspect(
    symbol: Annotated[str, typer.Option("--symbol", "-s")] = ...,  # type: ignore[assignment]
    kind: Annotated[str, typer.Option("--kind", "-k")] = "candles",
    timeframe: Annotated[str | None, typer.Option("--timeframe", "-t")] = None,
    head: Annotated[int, typer.Option("--head")] = 5,
    tail: Annotated[int, typer.Option("--tail")] = 5,
) -> None:
    """Inspect stored series head/tail + quality summary."""
    configure_logging(level="INFO")
    try:
        engine = _engine(connect_mt5=False)
        payload = engine.inspect(
            symbol, SeriesKind(kind), timeframe=timeframe, head=head, tail=tail
        )
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"[red]data inspect failed:[/red] {exc}")
        raise typer.Exit(1) from exc
    console.print_json(json.dumps(payload, default=str))


@data_app.command("stats")
def data_stats(
    symbol: Annotated[str | None, typer.Option("--symbol", "-s")] = None,
) -> None:
    """Show stored series statistics (SQLite metadata + parquet sizes)."""
    configure_logging(level="INFO")
    try:
        engine = _engine(connect_mt5=False)
        stats = engine.stats(symbol=symbol)
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"[red]data stats failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    table = Table(title="market data stats")
    table.add_column("symbol")
    table.add_column("kind")
    table.add_column("tf")
    table.add_column("rows")
    table.add_column("first")
    table.add_column("last")
    table.add_column("bytes")
    table.add_column("hash")
    for s in stats:
        table.add_row(
            s.symbol,
            s.kind.value,
            s.timeframe or "-",
            str(s.row_count),
            s.first_time.isoformat() if s.first_time else "-",
            s.last_time.isoformat() if s.last_time else "-",
            str(s.parquet_bytes),
            (s.content_hash or "-")[:12],
        )
    console.print(table)
    console.print(f"available timeframes: {', '.join(AVAILABLE_TIMEFRAMES)}")
