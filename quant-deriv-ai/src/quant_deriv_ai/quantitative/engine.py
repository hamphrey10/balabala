"""Quantitative Research Engine — stats lab + edge probes (LOT-005).

Research / analysis only. Never places orders.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from quant_deriv_ai.core.exceptions import QuantDerivError
from quant_deriv_ai.core.logging import get_logger
from quant_deriv_ai.quantitative.causality import assert_min_forward_lag, run_causality_suite
from quant_deriv_ai.quantitative.edge import (
    evaluate_edge,
    momentum_sign_probe,
    rsi_threshold_probe,
)
from quant_deriv_ai.quantitative.models import (
    CausalityStatus,
    EdgeMetrics,
    ResearchReport,
    ReturnStats,
)
from quant_deriv_ai.quantitative.reports import write_report
from quant_deriv_ai.quantitative.stats_lab import describe_series, summarize_returns

log = get_logger(__name__)


class QuantitativeResearchError(QuantDerivError):
    """Raised for quantitative research engine failures."""


class QuantitativeResearchEngine:
    """Stats lab, causal edge probes, and research reports.

    This engine has no MT5 write APIs and never places orders.
    """

    def __init__(
        self,
        *,
        min_forward_lag: int = 1,
        default_forward_horizon: int = 1,
        reports_dir: str = "reports",
        annualization_factor: float = 252.0,
        edge_min_observations: int = 30,
        momentum_lookback: int = 10,
        rsi_period: int = 14,
        rsi_low: float = 30.0,
        rsi_high: float = 70.0,
        return_method: str = "log",
    ) -> None:
        self.min_forward_lag = assert_min_forward_lag(min_forward_lag)
        self.default_forward_horizon = max(1, int(default_forward_horizon))
        self.reports_dir = reports_dir
        self.annualization_factor = float(annualization_factor)
        self.edge_min_observations = int(edge_min_observations)
        self.momentum_lookback = int(momentum_lookback)
        self.rsi_period = int(rsi_period)
        self.rsi_low = float(rsi_low)
        self.rsi_high = float(rsi_high)
        self.return_method = return_method

    @classmethod
    def from_config(cls, cfg: Mapping[str, Any] | None = None) -> QuantitativeResearchEngine:
        raw = dict(cfg or {})
        return cls(
            min_forward_lag=int(raw.get("min_forward_lag", 1)),
            default_forward_horizon=int(raw.get("default_forward_horizon", 1)),
            reports_dir=str(raw.get("reports_dir", "reports")),
            annualization_factor=float(raw.get("annualization_factor", 252.0)),
            edge_min_observations=int(raw.get("edge_min_observations", 30)),
            momentum_lookback=int(raw.get("momentum_lookback", 10)),
            rsi_period=int(raw.get("rsi_period", 14)),
            rsi_low=float(raw.get("rsi_low", 30.0)),
            rsi_high=float(raw.get("rsi_high", 70.0)),
            return_method=str(raw.get("return_method", "log")),
        )

    def stats(
        self,
        frame: pd.DataFrame,
        *,
        symbol: str = "UNKNOWN",
        timeframe: str = "M1",
    ) -> ResearchReport:
        """Compute descriptive + return statistics (no edge probes)."""
        self._require_close(frame)
        close = frame["close"].astype(float)
        returns = self._return_stats(close)
        price = describe_series(close, name="close")
        as_of = self._as_of(frame)
        return ResearchReport(
            symbol=symbol,
            timeframe=timeframe,
            as_of=as_of,
            bar_count=len(frame),
            generated_at=datetime.now(tz=UTC),
            returns=returns,
            price_stats=price,
            summary=self._stats_summary(returns),
            meta={"no_orders": True, "mode": "stats"},
        )

    def edge(
        self,
        frame: pd.DataFrame,
        *,
        symbol: str = "UNKNOWN",
        timeframe: str = "M1",
        forward_lag: int | None = None,
        forward_horizon: int | None = None,
        probes: Sequence[str] | None = None,
    ) -> ResearchReport:
        """Run built-in research edge probes (not trading strategies)."""
        self._require_close(frame)
        close = frame["close"].astype(float)
        lag = assert_min_forward_lag(
            forward_lag if forward_lag is not None else self.min_forward_lag,
            minimum=self.min_forward_lag,
        )
        horizon = forward_horizon if forward_horizon is not None else self.default_forward_horizon
        if horizon < 1:
            raise QuantitativeResearchError(f"forward_horizon must be >= 1, got {horizon}")

        selected = list(probes) if probes is not None else ["momentum_sign", "rsi_threshold"]
        edges = self._run_probes(close, lag=lag, horizon=horizon, probes=selected)
        causality = run_causality_suite(close, lag=lag, horizon=horizon)
        returns = self._return_stats(close)
        as_of = self._as_of(frame)
        return ResearchReport(
            symbol=symbol,
            timeframe=timeframe,
            as_of=as_of,
            bar_count=len(frame),
            generated_at=datetime.now(tz=UTC),
            returns=returns,
            price_stats=describe_series(close, name="close"),
            edge_probes=edges,
            causality=causality,
            summary=self._edge_summary(edges, causality),
            meta={
                "no_orders": True,
                "mode": "edge",
                "probes": selected,
                "forward_lag": lag,
                "forward_horizon": horizon,
            },
        )

    def report(
        self,
        frame: pd.DataFrame,
        *,
        symbol: str = "UNKNOWN",
        timeframe: str = "M1",
        forward_lag: int | None = None,
        forward_horizon: int | None = None,
        probes: Sequence[str] | None = None,
        output_path: str | Path | None = None,
        fmt: str = "markdown",
    ) -> ResearchReport:
        """Full research report (stats + edge + causality); optionally persist."""
        result = self.edge(
            frame,
            symbol=symbol,
            timeframe=timeframe,
            forward_lag=forward_lag,
            forward_horizon=forward_horizon,
            probes=probes,
        )
        result.meta["mode"] = "report"
        if output_path is not None:
            path = write_report(result, output_path, fmt=fmt)
            result.meta["report_path"] = str(path)
            log.info("research report written path={}", path)
        return result

    def stats_from_store(
        self,
        root: str | Path,
        *,
        symbol: str,
        timeframe: str,
    ) -> ResearchReport:
        frame = self._load_candles(root, symbol=symbol, timeframe=timeframe)
        return self.stats(frame, symbol=symbol, timeframe=timeframe)

    def edge_from_store(
        self,
        root: str | Path,
        *,
        symbol: str,
        timeframe: str,
        forward_lag: int | None = None,
        forward_horizon: int | None = None,
        probes: Sequence[str] | None = None,
    ) -> ResearchReport:
        frame = self._load_candles(root, symbol=symbol, timeframe=timeframe)
        return self.edge(
            frame,
            symbol=symbol,
            timeframe=timeframe,
            forward_lag=forward_lag,
            forward_horizon=forward_horizon,
            probes=probes,
        )

    def report_from_store(
        self,
        root: str | Path,
        *,
        symbol: str,
        timeframe: str,
        forward_lag: int | None = None,
        forward_horizon: int | None = None,
        probes: Sequence[str] | None = None,
        output_path: str | Path | None = None,
        fmt: str = "markdown",
    ) -> ResearchReport:
        frame = self._load_candles(root, symbol=symbol, timeframe=timeframe)
        if output_path is None:
            out_dir = Path(self.reports_dir)
            stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
            ext = "md" if fmt.strip().lower() in {"md", "markdown"} else "json"
            output_path = out_dir / f"{symbol}_{timeframe}_{stamp}.{ext}"
        return self.report(
            frame,
            symbol=symbol,
            timeframe=timeframe,
            forward_lag=forward_lag,
            forward_horizon=forward_horizon,
            probes=probes,
            output_path=output_path,
            fmt=fmt,
        )

    def _run_probes(
        self,
        close: pd.Series,
        *,
        lag: int,
        horizon: int,
        probes: Sequence[str],
    ) -> list[EdgeMetrics]:
        out: list[EdgeMetrics] = []
        for name in probes:
            key = str(name).strip().lower()
            if key in {"momentum_sign", "momentum", "mom"}:
                signal = momentum_sign_probe(close, lookback=self.momentum_lookback)
                probe_name = f"momentum_sign_{self.momentum_lookback}"
            elif key in {"rsi_threshold", "rsi"}:
                signal = rsi_threshold_probe(
                    close,
                    period=self.rsi_period,
                    low=self.rsi_low,
                    high=self.rsi_high,
                )
                probe_name = f"rsi_threshold_{self.rsi_period}"
            else:
                raise QuantitativeResearchError(f"unknown edge probe: {name!r}")
            out.append(
                evaluate_edge(
                    signal,
                    close,
                    probe_name=probe_name,
                    forward_lag=lag,
                    forward_horizon=horizon,
                    method=self.return_method,
                    min_observations=self.edge_min_observations,
                )
            )
        return out

    def _return_stats(self, close: pd.Series) -> ReturnStats:
        return summarize_returns(
            close,
            method=self.return_method,
            annualization_factor=self.annualization_factor,
        )

    @staticmethod
    def _load_candles(root: str | Path, *, symbol: str, timeframe: str) -> pd.DataFrame:
        from quant_deriv_ai.market_data.models import SeriesKind
        from quant_deriv_ai.persistence.store import MarketDataStore

        store = MarketDataStore(root)
        frame = store.read_working(symbol=symbol, kind=SeriesKind.CANDLES, timeframe=timeframe)
        if frame.empty:
            raise QuantitativeResearchError(
                f"no working candles for {symbol} {timeframe} under {root}"
            )
        return frame

    @staticmethod
    def _require_close(frame: pd.DataFrame) -> None:
        if "close" not in frame.columns:
            raise QuantitativeResearchError("frame missing close column")
        if frame.empty:
            raise QuantitativeResearchError("cannot analyze empty frame")

    @staticmethod
    def _as_of(frame: pd.DataFrame) -> datetime | None:
        if "time" not in frame.columns or frame.empty:
            return None
        raw = pd.Timestamp(frame["time"].iloc[-1]).to_pydatetime()
        if not isinstance(raw, datetime):
            return None
        return raw

    @staticmethod
    def _stats_summary(returns: ReturnStats) -> str:
        d = returns.descriptive
        return (
            f"Returns({returns.method}): n={returns.return_count}, "
            f"mean={d.mean}, std={d.std}, "
            f"hit+={returns.hit_rate_positive}, ann_vol={returns.annualized_vol}. "
            "Research only — no orders."
        )

    @staticmethod
    def _edge_summary(
        edges: list[EdgeMetrics],
        causality: list[Any],
    ) -> str:
        failed = [c for c in causality if getattr(c, "status", None) is CausalityStatus.FAIL]
        if failed:
            return (
                f"Causality FAIL ({len(failed)} check(s)) — edge metrics must not be trusted. "
                "No orders."
            )
        if not edges:
            return "No edge probes run. Research only — no orders."
        parts = [f"{e.probe_name}={e.verdict.value}" for e in edges]
        return "Edge probes: " + ", ".join(parts) + ". Research only — no orders."
