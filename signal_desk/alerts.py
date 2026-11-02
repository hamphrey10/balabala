"""Alertes signal actif (false → true) — fichier store + Telegram optionnel."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from signal_desk.analysis import SignalResult, analyze
from signal_desk.data import INSTRUMENTS, fetch_h4
from signal_desk.sizing import WEEK_RISK_USD, LadderSizing, build_week_ladder

DEFAULT_ALERT_DIR = Path("/cursor/stores/self/docs")
STATE_FILENAME = "alerte-state.json"
LOG_FILENAME = "alerte-log.txt"
ACTIVE_FILENAME = "alerte-active.md"


@dataclass(frozen=True)
class AlertEvent:
    symbol: str
    body_fr: str
    body_plain_fr: str
    fingerprint: str
    telegram_sent: bool = False
    telegram_note_fr: str = ""


def alert_dir() -> Path:
    raw = os.environ.get("SIGNAL_DESK_ALERT_DIR")
    return Path(raw) if raw else DEFAULT_ALERT_DIR


def _state_path() -> Path:
    return alert_dir() / STATE_FILENAME


def _log_path() -> Path:
    return alert_dir() / LOG_FILENAME


def active_alert_path() -> Path:
    return alert_dir() / ACTIVE_FILENAME


def telegram_configured() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()) and bool(
        os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    )


def _load_state() -> dict[str, dict[str, object]]:
    path = _state_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _save_state(state: dict[str, dict[str, object]]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _append_log(line: str) -> None:
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")


def _fingerprint(signal: SignalResult, ladder: LadderSizing) -> str:
    tp_part = "/".join(f"{s.price:.4f}" for s in ladder.slices) or f"{signal.take_profit_1:.4f}"
    raw = (
        f"{signal.symbol}|{signal.order_type_fr}|{signal.entry_mid:.4f}|"
        f"{signal.stop_loss:.4f}|{ladder.mode}|{ladder.total_lots:.2f}|{tp_part}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _format_price(symbol: str, value: float) -> str:
    if symbol == "XAGUSD":
        return f"{value:.4f}"
    return f"{value:.2f}"


def _sizing_for_alert(signal: SignalResult) -> LadderSizing | None:
    ladder = build_week_ladder(signal, WEEK_RISK_USD)
    if ladder.mode == "off":
        return None
    if ladder.total_risk_at_stop_usd > WEEK_RISK_USD + 0.01:
        return None
    return ladder


def _alert_lines(signal: SignalResult, ladder: LadderSizing) -> tuple[str, str]:
    entry = _format_price(signal.symbol, signal.entry_mid)
    stop = _format_price(signal.symbol, signal.stop_loss)
    risk = f"{ladder.total_risk_at_stop_usd:.2f}"

    if ladder.mode == "ladder_4x":
        tps = " / ".join(_format_price(signal.symbol, s.price) for s in ladder.slices)
        lots_md = f"**{ladder.total_lots:.2f} lot** (4×{ladder.slice_lots:.2f})"
        lots_plain = f"{ladder.total_lots:.2f} lot (4×{ladder.slice_lots:.2f})"
        tp_md = f"TP **{tps}**"
        tp_plain = f"TP {tps}"
    else:
        tp = _format_price(signal.symbol, signal.take_profit_1)
        lots_md = f"**{ladder.total_lots:.2f} lot**"
        lots_plain = f"{ladder.total_lots:.2f} lot"
        tp_md = f"TP unique **{tp}** (~1R)"
        tp_plain = f"TP unique {tp} (~1R)"

    md = (
        f"**{signal.symbol}** — tu poses **{signal.order_type_fr}** à **{entry}**, "
        f"{lots_md}, stop **{stop}**, {tp_md}, risque au stop **~{risk} USD** "
        f"(budget Deriv {WEEK_RISK_USD:.0f} USD)."
    )
    plain = (
        f"{signal.symbol} — tu poses {signal.order_type_fr} à {entry}, "
        f"{lots_plain}, stop {stop}, {tp_plain}, risque au stop ~{risk} USD "
        f"(budget Deriv {WEEK_RISK_USD:.0f} USD)."
    )
    return md, plain


def format_alert_fr(signal: SignalResult, ladder: LadderSizing, ts: str) -> str:
    md, _plain = _alert_lines(signal, ladder)
    return md


def send_telegram_message(text: str) -> tuple[bool, str]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return False, "Envoi Telegram en attente : définir TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if resp.status != 200:
                return False, f"Telegram HTTP {resp.status}"
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return False, "Telegram : réponse JSON invalide."
            if not data.get("ok"):
                desc = str(data.get("description", raw))[:200]
                return False, f"Telegram refusé : {desc}"
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:200]
        return False, f"Telegram refusé ({exc.code}) : {body}"
    except urllib.error.URLError as exc:
        return False, f"Telegram indisponible : {exc.reason}"

    return True, "Message Telegram envoyé."


def load_all_signals() -> tuple[list[SignalResult], str | None]:
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
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{symbol} : {exc}")
    err_msg = " | ".join(errors) if errors else None
    return results, err_msg


def check_alerts(*, write: bool = True) -> list[AlertEvent]:
    """Détecte les passages signal_active false → true, fichier store + Telegram."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    state = _load_state()
    events: list[AlertEvent] = []
    signals, _fetch_err = load_all_signals()

    for signal in signals:
        sym = signal.symbol
        prev = state.get(sym, {})
        alert_ack = bool(prev.get("signal_active", False))
        last_fp = str(prev.get("last_alert_fingerprint", ""))

        if not signal.signal_active:
            state[sym] = {
                "signal_active": False,
                "last_alert_fingerprint": last_fp,
            }
            continue

        ladder = _sizing_for_alert(signal)
        if ladder is None:
            # Pas de plan sous budget : ne pas consommer la bascule false→true.
            state[sym] = {
                "signal_active": alert_ack,
                "last_alert_fingerprint": last_fp,
            }
            continue

        fp = _fingerprint(signal, ladder)
        if alert_ack and fp == last_fp:
            state[sym] = {
                "signal_active": True,
                "last_alert_fingerprint": last_fp,
            }
            continue

        body_md, body_plain = _alert_lines(signal, ladder)
        sent, tg_note = (False, "")
        if write:
            sent, tg_note = send_telegram_message(body_plain)
        events.append(
            AlertEvent(
                symbol=sym,
                body_fr=body_md,
                body_plain_fr=body_plain,
                fingerprint=fp,
                telegram_sent=sent,
                telegram_note_fr=tg_note,
            )
        )
        state[sym] = {"signal_active": True, "last_alert_fingerprint": fp}
        if write:
            tg_flag = "telegram_ok" if sent else "telegram_pending"
            _append_log(
                f"{datetime.now(timezone.utc).isoformat()} {sym} fp={fp} alerted {tg_flag}"
            )

    if write:
        _save_state(state)
        if events:
            if telegram_configured():
                channel_line = "*Canal : Telegram.*"
            else:
                channel_line = (
                    "*Envoi Telegram en attente* — définir `TELEGRAM_BOT_TOKEN` "
                    "et `TELEGRAM_CHAT_ID`."
                )
            tg_lines = [f"- {ev.symbol} : {ev.telegram_note_fr}" for ev in events]
            doc = (
                f"# Alerte signal actif\n\n"
                f"*Généré : {ts}.*\n\n"
                f"{channel_line}\n\n"
                + "\n\n".join(e.body_fr for e in events)
                + "\n\n## Envoi\n\n"
                + "\n".join(tg_lines)
                + "\n"
            )
            path = active_alert_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(doc, encoding="utf-8")

    return events


def main() -> None:
    events = check_alerts(write=True)
    if not events:
        print("Aucune nouvelle alerte (pas de bascule false → true, ou doublon déjà loggé).")
        return
    for ev in events:
        print(ev.body_plain_fr)
        print(ev.telegram_note_fr)


if __name__ == "__main__":
    main()
