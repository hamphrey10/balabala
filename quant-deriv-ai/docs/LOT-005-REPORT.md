# LOT-005 Report — Quantitative Research Agent

**Verdict: PASS**

Date (UTC): 2026-11-27T14:11:59Z  
Package root: `/agent/repos/balabala/quant-deriv-ai/`  
Worker: `bc-634d7d6b-b13a-5221-b61a-0dbce8f3b305`  
Python: 3.12.3 on Linux x86_64  
Base branch: `cursor/lot-004-technical-analysis-5fc4` (LOT-004)

---

## Plan

1. Read permanent docs + `.cursor/rules/*` + LOT-004 foundation
2. Implement stats lab (returns, descriptive, rolling, autocorr)
3. Implement causal edge probes + look-ahead guards (`forward_lag >= 1`)
4. Research reports (Pydantic + Markdown/JSON writer)
5. CLI: `quant research stats|edge|report`
6. Tests + pytest / ruff / mypy executed for real

---

## Deliverables

| Item | Path |
| --- | --- |
| Stats lab | `src/quant_deriv_ai/quantitative/stats_lab.py` |
| Causality | `src/quant_deriv_ai/quantitative/causality.py` |
| Edge probes | `src/quant_deriv_ai/quantitative/edge.py` |
| Reports | `src/quant_deriv_ai/quantitative/reports.py` |
| Engine | `src/quant_deriv_ai/quantitative/engine.py` |
| Agent | `src/quant_deriv_ai/quantitative/agent.py` |
| Models | `src/quant_deriv_ai/quantitative/models.py` (`ResearchReport`, …) |
| CLI | `src/quant_deriv_ai/cli/research_cmds.py` |
| Config | `config/default.yaml` → `quantitative:` |
| Tests | `tests/test_stats_lab.py`, `test_edge_metrics.py`, `test_quantitative_engine.py`, `test_research_cli.py` |
| This report | `docs/LOT-005-REPORT.md` |

### CLI commands

- `quant research stats`
- `quant research edge`
- `quant research report`

---

## Mandatory checks (executed for real)

| Check | Command | Exit | Result |
| --- | --- | --- | --- |
| Pytest | `python3.12 -m pytest` | 0 | **123 passed, 2 skipped** |
| Ruff | `ruff check src tests` | 0 | **All checks passed** |
| MyPy | `mypy src/quant_deriv_ai` | 0 | **Success** (74 source files) |
| CLI research | `quant research --help` | 0 | `stats` / `edge` / `report` listed |

Skipped tests (honest BLOCKED from prior lots, not PASS):

- `tests/test_mt5_integration.py::test_real_demo_connect_account_symbols_positions`
- `tests/test_market_data_integration.py::test_real_demo_market_data_download`
- Reason: `BLOCKED: OS=Linux — official MetaTrader5 Python bridge requires Windows + local MT5 terminal`

---

## Features vs requirements

| Requirement | Status |
| --- | --- |
| Stats lab | `stats_lab.py` (returns, describe, rolling, autocorr, corr matrix) |
| Edge metrics | `edge.py` + probes `momentum_sign`, `rsi_threshold` |
| Anti look-ahead | `causality.py` (`lag>=1`, prefix/mutation, signal-bar independence) |
| Research reports | `ResearchReport` + Markdown/JSON writer |
| CLI | `quant research stats\|edge\|report` |
| Agent | `QuantitativeResearchAgent` |
| No orders | Confirmed (`meta.no_orders=True`; no order APIs in package) |
| Probes ≠ strategies | Documented; no `STRATEGY_REGISTRY` entries added |

---

## Out of scope (confirmed)

- No order placement
- No live/real trading
- No trading strategies (probes are research-only)
- No risk-engine decisions
- Real MT5 DEMO download remains **BLOCKED** on this Linux host (inherited)

---

## Notes

- Stacked on LOT-004 branch `cursor/lot-004-technical-analysis-5fc4`.
- Overall **PASS** for unit/causality/lint/typecheck/CLI controls that were executed and green.
