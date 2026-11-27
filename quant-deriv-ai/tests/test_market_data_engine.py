"""MarketDataEngine tests with a mock MT5-like source (no real terminal)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from quant_deriv_ai.config.settings import DataSettings
from quant_deriv_ai.execution.mt5.models import Candle, TickData
from quant_deriv_ai.market_data.engine import MarketDataEngine
from quant_deriv_ai.market_data.models import SeriesKind
from quant_deriv_ai.market_data.timeframes import AVAILABLE_TIMEFRAMES


class MockSource:
    def __init__(self) -> None:
        self.selected: list[str] = []

    def symbol_select(self, symbol: str, enable: bool = True) -> bool:
        self.selected.append(symbol)
        return enable

    def copy_rates_range(
        self,
        symbol: str,
        timeframe: str | int,
        date_from: datetime,
        date_to: datetime,
    ) -> list[Candle]:
        tf = str(timeframe).upper() if not isinstance(timeframe, int) else "M1"
        start = date_from.astimezone(UTC) if date_from.tzinfo else date_from.replace(tzinfo=UTC)
        end = date_to.astimezone(UTC) if date_to.tzinfo else date_to.replace(tzinfo=UTC)
        out: list[Candle] = []
        t = start.replace(second=0, microsecond=0)
        step = timedelta(minutes=1)
        i = 0
        while t <= end and i < 120:
            price = 100.0 + i * 0.01
            out.append(
                Candle(
                    symbol=symbol,
                    timeframe=tf,
                    time=t,
                    open=price,
                    high=price + 0.05,
                    low=price - 0.05,
                    close=price,
                    tick_volume=10,
                    spread=1,
                    real_volume=0,
                )
            )
            t += step
            i += 1
        return out

    def copy_ticks_from(
        self,
        symbol: str,
        date_from: datetime,
        count: int,
        *,
        flags: int | None = None,
    ) -> list[TickData]:
        _ = flags
        start = date_from.astimezone(UTC) if date_from.tzinfo else date_from.replace(tzinfo=UTC)
        return [
            TickData(
                symbol=symbol,
                time=start + timedelta(seconds=i),
                bid=1.1 + i * 0.0001,
                ask=1.1001 + i * 0.0001,
                last=0.0,
                volume=1.0,
                flags=0,
            )
            for i in range(count)
        ]

    def copy_ticks_range(
        self,
        symbol: str,
        date_from: datetime,
        date_to: datetime,
        *,
        flags: int | None = None,
    ) -> list[TickData]:
        _ = date_to
        return self.copy_ticks_from(symbol, date_from, 50, flags=flags)


def test_available_timeframes() -> None:
    assert AVAILABLE_TIMEFRAMES == ("M1", "M5", "M15", "M30", "H1", "H4", "D1")


def test_download_candles_and_validate(tmp_path: Path) -> None:
    engine = MarketDataEngine.from_root(
        tmp_path / "data",
        source=MockSource(),
        settings=DataSettings(freshness_max_age_s=31_536_000),
    )
    start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    end = start + timedelta(minutes=30)
    result = engine.download_candles("EURUSD", "M1", start, end)
    assert result.rows_written > 0
    assert result.quality is not None
    inspect = engine.inspect("EURUSD", SeriesKind.CANDLES, timeframe="M1")
    assert inspect["row_count"] == result.rows_written


def test_multi_instrument_multi_tf(tmp_path: Path) -> None:
    engine = MarketDataEngine.from_root(
        tmp_path / "data",
        source=MockSource(),
        settings=DataSettings(freshness_max_age_s=31_536_000),
    )
    start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    results = engine.download_multi(
        ["EURUSD", "XAUUSD"],
        timeframes=["M1", "M5"],
        date_from=start,
        date_to=start + timedelta(minutes=10),
        include_ticks=True,
    )
    # 2 symbols * 2 tfs + 2 tick series
    assert len(results) == 6
    stats = engine.stats()
    assert len(stats) >= 6


def test_update_incremental(tmp_path: Path) -> None:
    engine = MarketDataEngine.from_root(
        tmp_path / "data",
        source=MockSource(),
        settings=DataSettings(freshness_max_age_s=31_536_000),
    )
    start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    engine.download_candles("EURUSD", "M1", start, start + timedelta(minutes=5))
    upd = engine.update_candles("EURUSD", "M1")
    assert upd.kind is SeriesKind.CANDLES
    assert upd.rows_added >= 0


def test_pin_version_from_download(tmp_path: Path) -> None:
    engine = MarketDataEngine.from_root(
        tmp_path / "data",
        source=MockSource(),
        settings=DataSettings(freshness_max_age_s=31_536_000),
    )
    start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    result = engine.download_candles(
        "EURUSD",
        "M1",
        start,
        start + timedelta(minutes=5),
        pin_version="bt-001",
    )
    assert result.version == "bt-001"
    manifest = engine.store.assert_immutable_untouched("EURUSD_candles_M1", "bt-001")
    assert manifest.row_count == result.rows_written


def test_utc_normalization(tmp_path: Path) -> None:
    class NaiveSource(MockSource):
        def copy_rates_range(
            self,
            symbol: str,
            timeframe: str | int,
            date_from: datetime,
            date_to: datetime,
        ) -> list[Candle]:
            candles = super().copy_rates_range(symbol, timeframe, date_from, date_to)
            # Strip tz to simulate naive broker timestamps
            return [
                c.model_copy(update={"time": c.time.replace(tzinfo=None)}) for c in candles
            ]

    engine = MarketDataEngine.from_root(
        tmp_path / "data",
        source=NaiveSource(),
        settings=DataSettings(freshness_max_age_s=31_536_000),
    )
    start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    engine.download_candles("EURUSD", "M1", start, start + timedelta(minutes=3))
    frame = engine.store.read_working(
        symbol="EURUSD", kind=SeriesKind.CANDLES, timeframe="M1"
    )
    assert str(frame["time"].dtype) == "datetime64[ns, UTC]"


def test_market_data_agent_stats(tmp_path: Path) -> None:
    from quant_deriv_ai.agents.base import AgentContext
    from quant_deriv_ai.core.event_bus import EventBus
    from quant_deriv_ai.market_data.agent import MarketDataAgent

    engine = MarketDataEngine.from_root(tmp_path / "data", source=MockSource())
    start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    engine.download_candles("EURUSD", "M1", start, start + timedelta(minutes=2))
    agent = MarketDataAgent(
        AgentContext(name="mda", bus=EventBus(), config={"action": "stats"}),
        engine,
    )
    agent.start()
    assert agent.last_result is not None
    assert "stats" in agent.last_result
    agent.stop()


def test_no_order_side_effects_on_source(tmp_path: Path) -> None:
    source: Any = MockSource()
    engine = MarketDataEngine.from_root(tmp_path / "data", source=source)
    start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    engine.download_candles("EURUSD", "M1", start, start + timedelta(minutes=1))
    assert not hasattr(source, "order_send")
