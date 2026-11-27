"""DuckDB analysis views over Parquet market series."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from quant_deriv_ai.core.exceptions import PersistenceError
from quant_deriv_ai.market_data.models import SeriesKind


class DuckDbStore:
    """Registers Parquet files as DuckDB views for analytical queries."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.path))

    def register_parquet(
        self,
        *,
        view_name: str,
        parquet_path: Path,
    ) -> None:
        if not parquet_path.is_file():
            msg = f"parquet file missing for DuckDB view: {parquet_path}"
            raise PersistenceError(msg)
        safe = _safe_ident(view_name)
        # DuckDB rejects prepared params in CREATE VIEW — embed a quoted path.
        quoted = str(parquet_path.resolve()).replace("'", "''")
        with self._connect() as conn:
            conn.execute(
                f"CREATE OR REPLACE VIEW {safe} AS SELECT * FROM read_parquet('{quoted}')"
            )

    def query_df(self, sql: str, params: list[object] | None = None) -> pd.DataFrame:
        with self._connect() as conn:
            try:
                if params:
                    return conn.execute(sql, params).df()
                return conn.execute(sql).df()
            except Exception as exc:  # noqa: BLE001
                msg = f"duckdb query failed: {exc}"
                raise PersistenceError(msg) from exc

    def stats_for_view(self, view_name: str) -> dict[str, object]:
        safe = _safe_ident(view_name)
        frame = self.query_df(
            f"SELECT COUNT(*) AS n, MIN(time) AS first_time, MAX(time) AS last_time FROM {safe}"
        )
        if frame.empty:
            return {"row_count": 0, "first_time": None, "last_time": None}
        row = frame.iloc[0]
        return {
            "row_count": int(row["n"]),
            "first_time": row["first_time"],
            "last_time": row["last_time"],
        }

    def view_name(self, *, kind: SeriesKind, symbol: str, timeframe: str | None = None) -> str:
        base = f"{kind.value}_{_safe_ident(symbol)}"
        if kind is SeriesKind.CANDLES:
            if not timeframe:
                msg = "timeframe required for candle view"
                raise ValueError(msg)
            return f"{base}_{timeframe.upper()}"
        return base


def _safe_ident(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in value)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"v_{cleaned}"
    return cleaned
