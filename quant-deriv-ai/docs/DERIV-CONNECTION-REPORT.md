# Deriv Connection Report — Official WebSocket API (DEMO, read-only)

**Verdict: PASS** (unit + lint + typecheck; no live/demo account connected in this run)

Date (UTC): 2026-11-27  
Package root: `quant-deriv-ai/`  
Branch: `cursor/deriv-api-connection-b612` (from LOT-001)

---

## Correction

Primary broker connection is the **official Deriv WebSocket API**, not MetaTrader 5. MT5 scaffold remains optional/secondary.

---

## Official APIs used (documented)

| Item | Value / source |
| --- | --- |
| Register app + tokens | https://api.deriv.com |
| WebSocket URL | `wss://ws.derivws.com/websockets/v3?app_id=<DERIV_APP_ID>` ([deriv-com/deriv-api](https://github.com/deriv-com/deriv-api)) |
| Auth | `{"authorize":"<DERIV_API_TOKEN>"}` ([python-deriv-api](https://deriv-com.github.io/python-deriv-api/)) |
| Demo gate | `authorize.is_virtual == 1` (0 = real → permanent lock) |
| Balance | `{"balance": 1}` |
| Health | `{"ping": 1}` → `pong` |

**Intentionally absent:** `buy`, `sell`, purchase `proposal` flows, cashier — no orders.

---

## Env keys (never commit filled values; never log tokens)

| Key | Purpose |
| --- | --- |
| `DERIV_APP_ID` | Application id from api.deriv.com |
| `DERIV_API_TOKEN` | API token (DEMO/virtual account) |
| `DERIV_ENDPOINT` | Optional; default `wss://ws.derivws.com/websockets/v3` |

Documented in `.env.example`.

---

## Deliverables

| Item | Path |
| --- | --- |
| Connector | `src/quant_deriv_ai/execution/deriv/` |
| CLI | `quant deriv connect\|status\|account\|disconnect` |
| Config | `config/default.yaml` → `deriv:` |
| Tests | `tests/test_deriv_*.py` (mocked transport) |
| This report | `docs/DERIV-CONNECTION-REPORT.md` + store docs copy |

---

## Checks

| Check | Result |
| --- | --- |
| Pytest | **54 passed, 1 skipped** |
| Ruff | All checks passed |
| MyPy | Success |
| Order APIs on `DerivClient` | none |
| Real Deriv account connection | **not performed** |

---

## Out of scope

- No live/real trading
- No order placement
- No MT5 replacement removal (kept as optional scaffold)
