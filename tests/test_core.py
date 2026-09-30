import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai_engine import analyze, event_feed, rule_narrative
from config import RANGE_CONFIG, STOCKS
from market_data import add_indicators, build_demo_packet


def test_all_symbols_and_ranges_build_valid_ohlcv():
    for symbol in STOCKS:
        for range_key in RANGE_CONFIG:
            packet = build_demo_packet(symbol, range_key)
            assert packet.mode == "demo"
            assert not packet.frame.empty
            assert {"open", "high", "low", "close", "volume", "rsi", "macd"}.issubset(packet.frame.columns)
            assert (packet.frame.high >= packet.frame[["open", "close"]].max(axis=1)).all()
            assert (packet.frame.low <= packet.frame[["open", "close"]].min(axis=1)).all()


def test_signal_report_and_narrative_are_bounded():
    packet = build_demo_packet("NVDA", "3M")
    report = analyze(packet.frame)
    assert 0 <= report.score <= 100
    assert report.label in {"偏多", "中性", "偏空"}
    assert report.support <= report.resistance
    assert "NVDA" in rule_narrative("NVDA", report)
    assert event_feed("NVDA", packet.frame, report)


def test_indicators_do_not_mutate_input():
    packet = build_demo_packet("MSFT", "1M")
    raw = packet.frame[["open", "high", "low", "close", "volume"]].copy()
    result = add_indicators(raw)
    assert list(raw.columns) == ["open", "high", "low", "close", "volume"]
    assert "ma20" in result.columns and "macd_hist" in result.columns

