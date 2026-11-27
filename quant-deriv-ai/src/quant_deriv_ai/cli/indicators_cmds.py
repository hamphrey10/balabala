"""Typer subcommands: ``quant indicators list|validate``."""

from __future__ import annotations

import json
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from quant_deriv_ai.core.exceptions import QuantDerivError
from quant_deriv_ai.core.logging import configure_logging
from quant_deriv_ai.indicators.base import IndicatorError
from quant_deriv_ai.indicators.registry import get_indicator, list_indicators, validate_indicator

indicators_app = typer.Typer(help="Indicator registry (list / validate)")
console = Console()
err_console = Console(stderr=True)


@indicators_app.command("list")
def indicators_list(
    json_out: Annotated[bool, typer.Option("--json", help="Print JSON")] = False,
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="Filter by category"),
    ] = None,
) -> None:
    """List registered technical indicators."""
    configure_logging(level="INFO")
    specs = list_indicators()
    if category:
        specs = [s for s in specs if s.category.value == category.lower()]
    if json_out:
        console.print_json(json.dumps([s.model_dump(mode="json") for s in specs]))
        return
    table = Table(title="Indicators")
    table.add_column("Name")
    table.add_column("Category")
    table.add_column("Defaults")
    table.add_column("Outputs")
    table.add_column("Description")
    for spec in specs:
        table.add_row(
            spec.name,
            spec.category.value,
            json.dumps(spec.default_params, sort_keys=True),
            ", ".join(spec.outputs),
            spec.description,
        )
    console.print(table)


@indicators_app.command("validate")
def indicators_validate(
    name: Annotated[str, typer.Argument(help="Indicator name")],
    param: Annotated[
        list[str] | None,
        typer.Option("--param", "-p", help="param=value (repeatable)"),
    ] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Print JSON")] = False,
) -> None:
    """Validate an indicator name and optional parameters."""
    configure_logging(level="INFO")
    raw: dict[str, Any] = {}
    for item in param or []:
        if "=" not in item:
            err_console.print(f"[red]invalid --param {item!r}; expected key=value[/red]")
            raise typer.Exit(2)
        key, value = item.split("=", 1)
        raw[key.strip()] = _coerce(value.strip())
    try:
        merged = validate_indicator(name, raw)
        spec = get_indicator(name)
    except (IndicatorError, QuantDerivError) as exc:
        err_console.print(f"[red]invalid:[/red] {exc}")
        raise typer.Exit(1) from exc
    payload = {"name": spec.name, "params": merged, "outputs": spec.outputs, "ok": True}
    if json_out:
        console.print_json(json.dumps(payload))
        return
    console.print(f"[green]ok[/green] {spec.name} params={merged} outputs={spec.outputs}")


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
