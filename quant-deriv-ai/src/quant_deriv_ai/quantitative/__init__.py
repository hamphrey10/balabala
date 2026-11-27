"""Quantitative research package — stats lab, edge probes, reports (LOT-005)."""

from __future__ import annotations

from quant_deriv_ai.quantitative.agent import QuantitativeResearchAgent
from quant_deriv_ai.quantitative.engine import QuantitativeResearchEngine
from quant_deriv_ai.quantitative.models import (
    CausalityCheck,
    DescriptiveStats,
    EdgeMetrics,
    EdgeVerdict,
    ResearchReport,
    ReturnStats,
)

__all__ = [
    "CausalityCheck",
    "DescriptiveStats",
    "EdgeMetrics",
    "EdgeVerdict",
    "QuantitativeResearchAgent",
    "QuantitativeResearchEngine",
    "ResearchReport",
    "ReturnStats",
]
