"""Local signal desk — French UI, manual execution only."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from signal_desk.analysis import SignalResult, analyze
from signal_desk.data import INSTRUMENTS, fetch_h4
from signal_desk.sizing import CONTRACT_NOTE_FR, SymbolSizing, build_sizing

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Bureau de signaux", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

HORIZON_LABEL = "Swing H4 — XAUUSD & XAGUSD (horizon verrouillé)"


def _load_signals() -> tuple[list[SignalResult], str | None]:
    results: list[SignalResult] = []
    errors: list[str] = []
    for symbol in INSTRUMENTS:
        try:
            series = fetch_h4(symbol)
            results.append(
                analyze(
                    symbol,
                    series.df,
                    series.last_price,
                    series.price_note_fr,
                    series.data_source,
                )
            )
        except Exception as exc:  # noqa: BLE001 — surface per-symbol fetch failures in UI
            errors.append(f"{symbol} : {exc}")
    err_msg = " | ".join(errors) if errors else None
    return results, err_msg


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    signals, fetch_error = _load_signals()
    week_sizing: list[SymbolSizing] = [build_sizing(s) for s in signals]
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "signals": signals,
            "week_sizing": week_sizing,
            "contract_note": CONTRACT_NOTE_FR,
            "week_risk_usd": 100.0,
            "horizon": HORIZON_LABEL,
            "updated": updated,
            "fetch_error": fetch_error,
        },
    )


@app.get("/api/signals")
async def api_signals() -> dict:
    signals, fetch_error = _load_signals()
    return {
        "horizon": HORIZON_LABEL,
        "fetch_error": fetch_error,
        "signals": [
            {
                "symbol": s.symbol,
                "bias": s.bias.value,
                "side": s.side.value,
                "last_price": s.last_price,
                "price_note_fr": s.price_note_fr,
                "data_source": s.data_source,
                "signal_active": s.signal_active,
                "precondition_fr": s.precondition_fr,
                "entry_mid": s.entry_mid,
                "entry_zone": [s.entry_zone_low, s.entry_zone_high],
                "stop_loss": s.stop_loss,
                "take_profit_1": s.take_profit_1,
                "take_profit_2": s.take_profit_2,
                "reward_risk": s.reward_risk,
                "dist_entry_stop": s.dist_entry_stop,
                "dist_entry_tp1": s.dist_entry_tp1,
                "commentary": s.commentary,
                "order_type_fr": s.order_type_fr,
                "order_instruction_fr": s.order_instruction_fr,
                "order_trigger_price": s.order_trigger_price,
            }
            for s in signals
        ],
    }
