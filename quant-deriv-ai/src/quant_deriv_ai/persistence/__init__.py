"""Persistence layer — Parquet (history), DuckDB (analysis), SQLite (metadata)."""

from __future__ import annotations

from quant_deriv_ai.persistence.store import MarketDataStore

__all__ = ["MarketDataStore"]
