# LOT-002 Report — MetaTrader5 Python connector (DEMO-only, read-only)

**Verdict: PASS** (unit + lint + typecheck)  
**Integration (real DEMO terminal): BLOCKED**

Date (UTC): 2026-11-27  
Package root: `/cursor/stores/self/quant-deriv-ai/`  
Worker: `bc-033930ad-e0af-52f2-a6ae-7892e2e15fb5`  
Python: 3.12.3 on Linux x86_64

---

## Plan

1. Wait for LOT-001 scaffold (`pyproject.toml`, packages, `quant` CLI) — confirmed present
2. Read permanent docs + `dot-cursor/rules/*.mdc`
3. Research official MetaTrader5 Python APIs (MQL5 Reference) — do not invent APIs
4. Implement DEMO-only connector with live lock, retry/backoff, heartbeat, call serialization
5. Wire Typer CLI `quant mt5 …` (no order commands)
6. Unit tests with mocks; integration tests that skip as BLOCKED without terminal/creds
7. Run pytest / ruff / mypy for real; report honestly

---

## Official APIs used (documented)

Source: [MQL5 Python Integration](https://www.mql5.com/en/docs/python_metatrader5)

| API | Use in LOT-002 |
| --- | --- |
| `initialize` / `login` / `shutdown` / `version` / `last_error` | Connection lifecycle + errors |
| `account_info` / `terminal_info` | Account + server + DEMO verification (`trade_mode`) |
| `symbols_get` / `symbol_info` / `symbol_select` | Dynamic instrument discovery + characteristics |
| `copy_ticks_from` / `copy_rates_from_pos` / `copy_rates_range` | Ticks + OHLCV |
| `positions_get` / `history_deals_get` | Open positions + deal history (read-only) |

**Intentionally absent:** `order_send`, `order_check`, `order_calc_*` (no place/modify/close in this lot).

**Account trade modes** (ENUM_ACCOUNT_TRADE_MODE): DEMO=0, CONTEST=1, REAL=2. Only DEMO accepted; contest/real engage permanent `LiveAccountLock` forbidding further operations.

---

## Deliverables

| Item | Path |
| --- | --- |
| Connector package | `/cursor/stores/self/quant-deriv-ai/src/quant_deriv_ai/execution/mt5/` |
| Client | `client.py` — connect, heartbeat, reconnect+backoff, RLock serialization |
| Live lock | `live_lock.py` — blocks ANY op on non-DEMO |
| Credentials | `credentials.py` — env-only; `safe_dict()` redacts password |
| Models | `models.py` — account, terminal, symbol, tick, candle, position, deal |
| CLI | `/cursor/stores/self/quant-deriv-ai/src/quant_deriv_ai/cli/mt5_cmds.py` |
| Unit tests | `tests/test_mt5_*.py` |
| Integration | `tests/test_mt5_integration.py` (skip=BLOCKED on this host) |
| This report | `/cursor/stores/self/docs/LOT-002-REPORT.md` |

### CLI commands

- `quant mt5 connect`
- `quant mt5 status`
- `quant mt5 account`
- `quant mt5 symbols`
- `quant mt5 positions`
- `quant mt5 disconnect`

Credentials: `MT5_LOGIN` / `MT5_PASSWORD` / `MT5_SERVER` / optional `MT5_PATH` via `.env` (placeholders only in `.env.example`). Never logged.

---

## Mandatory checks (executed for real)

| Check | Command | Exit | Result |
| --- | --- | --- | --- |
| Pytest (unit + integration collect) | `python3.12 -m pytest -v` | 0 | **36 passed, 1 skipped** |
| Ruff | `python3.12 -m ruff check src tests` | 0 | **All checks passed** |
| MyPy | `python3.12 -m mypy src/quant_deriv_ai` | 0 | **Success** (39 source files) |
| No order methods on client | `dir(Mt5Client)` filter | 0 | **empty** (`order_*` absent) |
| CLI help | `quant mt5 --help` | 0 | six commands listed |

Skipped test (honest BLOCKED, not PASS):

- `tests/test_mt5_integration.py::test_real_demo_connect_account_symbols_positions`
- Reason: `BLOCKED: OS=Linux — official MetaTrader5 Python bridge requires Windows + local MT5 terminal`
- Also no `MT5_*` DEMO credentials configured in this environment

---

## Features vs requirements

| Requirement | Status |
| --- | --- |
| Detect MT5 terminal | Implemented (`detect_terminal` / `terminal_info`) |
| Init connection | Implemented (`initialize` + `login`) |
| Secure authentication | Env credentials; password redacted from logs/status |
| Account type verification | `trade_mode` must be DEMO |
| Server identification | From `account_info().server` |
| Account info (balance/equity/margin/currency) | `AccountSnapshot` |
| Dynamic instrument discovery | `symbols_get` |
| Symbol characteristics | `symbol_info` → `SymbolCharacteristics` |
| Ticks / OHLCV | `copy_ticks_from`, `copy_rates_*` |
| Open positions / deal history | `positions_get`, `history_deals_get` |
| MT5 error handling | `last_error` → `Mt5Error` / `Mt5ConnectionError` |
| Auto-reconnect, heartbeat, timeout, exp. backoff | Implemented on client |
| Serialize MT5 calls | `threading.RLock` |
| Strict LIVE lock | `LiveAccountLock` — forbids further ops |
| NO orders | Confirmed — no order APIs exposed |

---

## Out of scope (confirmed)

- No `order_send` / place / modify / close
- No live/real trading
- No trading strategies
- No real DEMO connection on this Linux agent host (BLOCKED)

---

## Notes

- Depends on LOT-001 scaffold at `/cursor/stores/self/quant-deriv-ai/` (present).
- Cursor rules remain under `/cursor/stores/self/dot-cursor/rules/` (agent-store blocks literal `.cursor/`).
- Overall **PASS** applies to unit/lint/typecheck controls that were executed and green. Real-terminal integration remains **BLOCKED** until a Windows DEMO host with credentials is available — not inventing a PASS for that check.

---

## Sync into hamphrey10/balabala

Synced together with LOT-001 under `quant-deriv-ai/` on branch `cursor/lot-001-python-foundation-b612` (base: LOT-000 PR #3). No order APIs present (`dir(Mt5Client)` order filter empty). Repo re-check: **36 passed, 1 skipped** (integration BLOCKED on Linux); ruff/mypy clean.
