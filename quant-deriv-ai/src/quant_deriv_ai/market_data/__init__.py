"""Market data engine — collect, validate, normalize, store Deriv MT5 series."""

from __future__ import annotations

from quant_deriv_ai.execution.mt5.models import Candle, SymbolCharacteristics, TickData
from quant_deriv_ai.market_data.agent import MarketDataAgent
from quant_deriv_ai.market_data.engine import MarketDataEngine
from quant_deriv_ai.market_data.models import (
    DatasetManifest,
    DownloadResult,
    QualityReport,
    SeriesKind,
    SeriesStats,
)
from quant_deriv_ai.market_data.timeframes import AVAILABLE_TIMEFRAMES

__all__ = [
    "AVAILABLE_TIMEFRAMES",
    "Candle",
    "DatasetManifest",
    "DownloadResult",
    "MarketDataAgent",
    "MarketDataEngine",
    "QualityReport",
    "SeriesKind",
    "SeriesStats",
    "SymbolCharacteristics",
    "TickData",
]
