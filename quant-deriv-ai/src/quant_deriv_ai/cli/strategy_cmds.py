"""Typer subcommands: ``quant strategy list|inspect|validate`` (no orders)."""

from __future__ import annotations

import json
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from quant_deriv_ai.core.exceptions import QuantDerivError
from quant_deriv_ai.core.logging import configure_logging
from quant_deriv_ai.strategies.base import StrategyError
from quant_deriv_ai.strategies.engine import StrategyEngine
from quant_deriv_ai.strategies.models import StrategyCategory, StrategyStatus

strategy_app = typer.Typer(
    help="Strategy registry (list / inspect / validate) — hypotheses only; no orders"
)
console = Console()
err_console = Console(stderr=True)


def _engine() -> StrategyEngine:
    return StrategyEngine.from_config()


@strategy_app.command("list")
def strategy_list(
    json_out: Annotated[bool, typer.Option("--json", help="Print JSON")] = False,
    status: Annotated[
        str | None,
        typer.Option("--status", "-s", help="Filter by status (e.g. hypothesis)"),
    ] = None,
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="Filter by category"),
    ] = None,
) -> None:
    """List registered experimental strategy hypotheses."""
    configure_logging(level="INFO")
    from quant_deriv_ai.strategies.registry import list_strategies

    try:
        st = StrategyStatus(status) if status else None
        cat = StrategyCategory(category) if category else None
        specs = list_strategies(status=st, category=cat)
    except (ValueError, StrategyError, QuantDerivError) as exc:
        err_console.print(f"[red]strategy list error:[/red] {exc}")
        raise typer.Exit(1) from exc

    if json_out:
        console.print_json(json.dumps([s.model_dump(mode="json") for s in specs]))
        return

    table = Table(title="Strategy Registry (hypotheses — no auto activation)")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Category")
    table.add_column("Status")
    table.add_column("Edge?")
    table.add_column("Auto?")
    table.add_column("Hypothesis")
    for spec in specs:
        table.add_row(
            spec.id,
            spec.name,
            spec.category.value,
            spec.status.value,
            "yes" if spec.edge_demonstrated else "no",
            "yes" if spec.auto_activate else "no",
            spec.hypothesis[:60] + ("…" if len(spec.hypothesis) > 60 else ""),
        )
    console.print(table)
    console.print(
        f"[dim]{len(specs)} strategies · no_orders=true · live_allowed=false[/dim]"
    )


@strategy_app.command("inspect")
def strategy_inspect(
    key: Annotated[str, typer.Argument(help="Strategy id (STR-001) or name")],
    json_out: Annotated[bool, typer.Option("--json", help="Print JSON")] = False,
) -> None:
    """Inspect one strategy hypothesis (metadata + safety flags)."""
    configure_logging(level="INFO")
    try:
        payload = _engine().inspect(key)
    except (StrategyError, QuantDerivError) as exc:
        err_console.print(f"[red]inspect error:[/red] {exc}")
        raise typer.Exit(1) from exc

    if json_out:
        console.print_json(json.dumps(payload))
        return

    console.print(f"[bold]{payload['id']}[/bold] — {payload['name']}")
    console.print(f"status: {payload['status']}  category: {payload['category']}")
    console.print(f"hypothesis: {payload['hypothesis']}")
    console.print(f"description: {payload['description']}")
    console.print(f"default_params: {json.dumps(payload['default_params'], sort_keys=True)}")
    console.print(f"signals: {', '.join(payload['signals'])}")
    safety = payload.get("safety", {})
    console.print(
        f"safety: no_orders={safety.get('no_orders')} "
        f"auto_activate={safety.get('auto_activate')} "
        f"live_allowed={safety.get('live_allowed')} "
        f"edge_demonstrated={safety.get('edge_demonstrated')}"
    )


@strategy_app.command("validate")
def strategy_validate(
    key: Annotated[str, typer.Argument(help="Strategy id or name")],
    param: Annotated[
        list[str] | None,
        typer.Option("--param", "-p", help="param=value (repeatable)"),
    ] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Print JSON")] = False,
) -> None:
    """Validate a strategy id/name and optional parameters."""
    configure_logging(level="INFO")
    raw: dict[str, Any] = {}
    for item in param or []:
        if "=" not in item:
            err_console.print(f"[red]invalid --param {item!r}; expected key=value[/red]")
            raise typer.Exit(2)
        k, value = item.split("=", 1)
        raw[k.strip()] = _coerce(value.strip())
    try:
        payload = _engine().validate(key, raw)
    except (StrategyError, QuantDerivError) as exc:
        err_console.print(f"[red]invalid:[/red] {exc}")
        raise typer.Exit(1) from exc

    if json_out:
        console.print_json(json.dumps(payload))
        return
    console.print(
        f"[green]ok[/green] {payload['id']} ({payload['name']}) "
        f"params={payload['params']} status={payload['status']} "
        f"no_orders={payload['no_orders']} auto_activate={payload['auto_activate']}"
    )


def _coerce(value: str) -> Any:
    lower = value.lower()
    if lower in {"true", "false"}:
        return lower == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value
