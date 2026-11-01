"""Fetch and prepare H4 OHLC series from Yahoo Finance (COMEX futures proxies)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import yfinance as yf

INSTRUMENTS: dict[str, dict[str, str]] = {
    "XAUUSD": {
        "yahoo_ticker": "GC=F",
        "label_fr": "Or (XAUUSD)",
        "price_note_fr": "Prix indicatif : future COMEX or (GC), pas le spot courtier.",
    },
    "XAGUSD": {
        "yahoo_ticker": "SI=F",
        "label_fr": "Argent (XAGUSD)",
        "price_note_fr": "Prix indicatif : future COMEX argent (SI), pas le spot courtier.",
    },
}


@dataclass(frozen=True)
class PriceSeries:
    symbol: str
    df: pd.DataFrame
    last_price: float
    price_note_fr: str
    data_source: str


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def fetch_h4(symbol: str, period: str = "60d") -> PriceSeries:
    meta = INSTRUMENTS[symbol]
    ticker = meta["yahoo_ticker"]
    raw = yf.download(ticker, period=period, interval="1h", progress=False, auto_adjust=True)
    raw = _flatten_columns(raw)
    if raw.empty:
        raise RuntimeError(f"Aucune donnée pour {ticker}")

    raw = raw.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    for col in ("open", "high", "low", "close"):
        if col not in raw.columns:
            raise RuntimeError(f"Colonne manquante {col} pour {ticker}")

    h4 = raw.resample("4h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()

    last_price = float(h4["close"].iloc[-1])
    return PriceSeries(
        symbol=symbol,
        df=h4,
        last_price=last_price,
        price_note_fr=meta["price_note_fr"],
        data_source=f"Yahoo Finance ({ticker}, 1h → H4)",
    )
