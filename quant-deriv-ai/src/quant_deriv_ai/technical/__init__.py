"""Technical analysis package (LOT-004) — independent of order execution."""

from __future__ import annotations

from quant_deriv_ai.technical.agent import TechnicalAnalysisAgent
from quant_deriv_ai.technical.engine import TechnicalAnalysisEngine, TechnicalAnalysisError
from quant_deriv_ai.technical.models import (
    BreakoutEvent,
    BreakoutSide,
    MTFConsensus,
    StructureBias,
    StructureLevel,
    SwingPoint,
    TechnicalSnapshot,
    TrendDirection,
    TrendState,
    VolumeCaveat,
)

__all__ = [
    "BreakoutEvent",
    "BreakoutSide",
    "MTFConsensus",
    "StructureBias",
    "StructureLevel",
    "SwingPoint",
    "TechnicalAnalysisAgent",
    "TechnicalAnalysisEngine",
    "TechnicalAnalysisError",
    "TechnicalSnapshot",
    "TrendDirection",
    "TrendState",
    "VolumeCaveat",
]
