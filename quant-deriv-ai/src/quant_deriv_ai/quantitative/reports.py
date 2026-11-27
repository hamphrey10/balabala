"""Research report rendering and persistence (LOT-005)."""

from __future__ import annotations

import json
from pathlib import Path

from quant_deriv_ai.core.exceptions import QuantDerivError
from quant_deriv_ai.quantitative.models import CausalityStatus, ResearchReport


class ReportError(QuantDerivError):
    """Raised when a research report cannot be written."""


def render_markdown(report: ResearchReport) -> str:
    """Render a :class:`ResearchReport` as Markdown (no invented metrics)."""
    lines: list[str] = [
        f"# Research Report — {report.symbol} {report.timeframe}",
        "",
        f"- Generated: `{report.generated_at}`",
        f"- As of: `{report.as_of}`",
        f"- Bars: `{report.bar_count}`",
        f"- No orders: `{report.meta.get('no_orders', True)}`",
        "",
        "## Summary",
        "",
        report.summary or "_No summary._",
        "",
    ]

    if report.price_stats is not None:
        ps = report.price_stats
        lines.extend(
            [
                "## Price statistics (close)",
                "",
                "| Metric | Value |",
                "| --- | --- |",
                f"| count | {ps.count} |",
                f"| mean | {_fmt(ps.mean)} |",
                f"| std | {_fmt(ps.std)} |",
                f"| min | {_fmt(ps.min)} |",
                f"| max | {_fmt(ps.max)} |",
                f"| median | {_fmt(ps.median)} |",
                f"| skew | {_fmt(ps.skew)} |",
                f"| excess kurtosis | {_fmt(ps.kurtosis)} |",
                "",
            ]
        )

    if report.returns is not None:
        rs = report.returns
        d = rs.descriptive
        lines.extend(
            [
                f"## Returns ({rs.method})",
                "",
                f"- Return observations: `{rs.return_count}`",
                f"- Hit rate (positive): `{_fmt(rs.hit_rate_positive)}`",
                f"- Annualized vol (factor={rs.annualization_factor}): `{_fmt(rs.annualized_vol)}`",
                "",
                "| Metric | Value |",
                "| --- | --- |",
                f"| mean | {_fmt(d.mean)} |",
                f"| std | {_fmt(d.std)} |",
                f"| skew | {_fmt(d.skew)} |",
                f"| excess kurtosis | {_fmt(d.kurtosis)} |",
                "",
            ]
        )
        if rs.autocorr:
            lines.extend(["### Autocorrelation", "", "| Lag | Corr |", "| --- | --- |"])
            for pt in rs.autocorr:
                lines.append(f"| {pt.lag} | {_fmt(pt.value)} |")
            lines.append("")

    if report.edge_probes:
        lines.extend(
            [
                "## Edge probes (research only)",
                "",
                "| Probe | Lag | Horizon | Active | Hit | Expectancy | Sharpe | Verdict |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for e in report.edge_probes:
            lines.append(
                f"| {e.probe_name} | {e.forward_lag} | {e.forward_horizon} | "
                f"{e.active_signals} | {_fmt(e.hit_rate)} | {_fmt(e.expectancy)} | "
                f"{_fmt(e.sharpe)} | {e.verdict.value} |"
            )
        lines.append("")
        lines.append(
            "_Probes are not trading strategies. Positive metrics do not authorize orders._"
        )
        lines.append("")

    if report.causality:
        lines.extend(
            [
                "## Causality checks",
                "",
                "| Check | Status | Detail |",
                "| --- | --- | --- |",
            ]
        )
        for c in report.causality:
            lines.append(f"| {c.name} | {c.status.value} | {c.detail} |")
        lines.append("")

    failed = [c for c in report.causality if c.status is CausalityStatus.FAIL]
    if failed:
        lines.append("**Causality FAIL present — do not trust edge metrics until fixed.**")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_report(
    report: ResearchReport,
    path: str | Path,
    *,
    fmt: str = "markdown",
) -> Path:
    """Write report to ``path`` as markdown or json."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    key = fmt.strip().lower()
    if key in {"md", "markdown"}:
        out.write_text(render_markdown(report), encoding="utf-8")
    elif key == "json":
        out.write_text(
            json.dumps(report.model_dump(mode="json"), indent=2, default=str) + "\n",
            encoding="utf-8",
        )
    else:
        raise ReportError(f"unsupported report format: {fmt!r}")
    return out


def _fmt(value: float | None) -> str:
    if value is None:
        return "—"
    if abs(value) >= 1000 or (abs(value) > 0 and abs(value) < 1e-4):
        return f"{value:.6g}"
    return f"{value:.6f}".rstrip("0").rstrip(".")
