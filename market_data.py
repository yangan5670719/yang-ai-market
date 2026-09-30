"""Market data adapters.

Demo mode is deterministic and exists only so the learning project can run
without credentials. Live mode uses Twelve Data and always exposes source and
timestamp metadata so simulated, delayed and live data cannot be confused.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import math
from typing import Any

import numpy as np
import pandas as pd

from config import RANGE_CONFIG, STOCKS


@dataclass
class MarketPacket:
    symbol: str
    frame: pd.DataFrame
    quote: dict[str, Any]
    fundamentals: dict[str, Any]
    source: str
    as_of: str
    mode: str
    warning: str = ""


class MarketDataError(RuntimeError):
    pass


def _seed(symbol: str) -> int:
    return int(hashlib.sha256(symbol.encode()).hexdigest()[:8], 16)


def _base_price(symbol: str) -> float:
    known = {
        "NVDA": 182.4, "INTC": 42.8, "MSFT": 515.2, "GOOG": 221.7,
        "LRCX": 151.6, "ENTG": 118.4, "C": 109.2, "FLEX": 71.5,
        "GE": 306.8, "EUV": 25.3,
    }
    return known.get(symbol, 100.0)


def _periods(range_key: str) -> int:
    return int(RANGE_CONFIG[range_key]["outputsize"])


def build_demo_packet(symbol: str, range_key: str) -> MarketPacket:
    """Generate reproducible OHLCV data, clearly marked as simulated."""
    cfg = RANGE_CONFIG[range_key]
    count = _periods(range_key)
    intraday = "min" in cfg["interval"]
    freq = "5min" if cfg["interval"] == "5min" else "15min" if intraday else "B"
    end = pd.Timestamp.now(tz="America/New_York").floor("min")
    index = pd.date_range(end=end, periods=count, freq=freq)
    rng = np.random.default_rng(_seed(symbol) + list(RANGE_CONFIG).index(range_key) * 97)
    base = _base_price(symbol)
    volatility = 0.004 if intraday else 0.018
    drift = np.linspace(-0.01, 0.025, count)
    returns = rng.normal(0.00025, volatility, count) + drift / max(count, 1)
    close = base * np.exp(np.cumsum(returns))
    open_ = np.r_[base, close[:-1]] * (1 + rng.normal(0, volatility / 3, count))
    spread = np.abs(rng.normal(volatility * 0.7, volatility * 0.25, count))
    high = np.maximum(open_, close) * (1 + spread)
    low = np.minimum(open_, close) * (1 - spread)
    volume = rng.lognormal(mean=14.2 if intraday else 17.2, sigma=0.45, size=count).astype(int)
    frame = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )
    frame = add_indicators(frame)
    latest = frame.iloc[-1]
    previous = frame.iloc[-2] if len(frame) > 1 else latest
    change = float(latest.close - previous.close)
    pct = change / float(previous.close) * 100 if previous.close else 0.0
    market_cap = latest.close * (10_000_000_000 + (_seed(symbol) % 15_000_000_000))
    quote = {
        "price": float(latest.close), "open": float(latest.open),
        "high": float(latest.high), "low": float(latest.low),
        "previous_close": float(previous.close), "volume": int(latest.volume),
        "change": change, "percent_change": pct,
    }
    fundamentals = {
        "market_cap": market_cap, "pe": 18 + _seed(symbol) % 32,
        "forward_pe": 14 + _seed(symbol) % 24, "peg": 0.8 + (_seed(symbol) % 30) / 10,
        "eps": 1.2 + (_seed(symbol) % 1200) / 100, "beta": 0.65 + (_seed(symbol) % 180) / 100,
        "week52_high": float(frame.high.max() * 1.12), "week52_low": float(frame.low.min() * 0.82),
    }
    return MarketPacket(
        symbol=symbol, frame=frame, quote=quote, fundamentals=fundamentals,
        source="SIMULATED · 教学演示", as_of=datetime.now(timezone.utc).isoformat(),
        mode="demo", warning="演示数据不是市场行情，不得用于交易判断。",
    )


class TwelveDataProvider:
    base_url = "https://api.twelvedata.com"

    def __init__(self, api_key: str, timeout: int = 12):
        if not api_key:
            raise ValueError("Twelve Data API key is required")
        self.api_key = api_key
        self.timeout = timeout

    def _get(self, endpoint: str, **params: Any) -> Any:
        import requests

        params["apikey"] = self.api_key
        response = requests.get(f"{self.base_url}/{endpoint}", params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("status") == "error":
            raise MarketDataError(payload.get("message", "Twelve Data request failed"))
        return payload

    def packet(self, symbol: str, range_key: str) -> MarketPacket:
        cfg = RANGE_CONFIG[range_key]
        raw = self._get(
            "time_series", symbol=symbol, interval=cfg["interval"],
            outputsize=cfg["outputsize"], format="JSON", timezone="America/New_York",
        )
        values = raw.get("values") or []
        if not values:
            raise MarketDataError(f"{symbol} 没有返回K线数据")
        frame = pd.DataFrame(values)
        frame["datetime"] = pd.to_datetime(frame["datetime"])
        frame = frame.set_index("datetime").sort_index()
        for col in ["open", "high", "low", "close", "volume"]:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        frame = add_indicators(frame.dropna(subset=["open", "high", "low", "close"]))

        quote_raw = self._get("quote", symbol=symbol)
        latest = frame.iloc[-1]
        previous = frame.iloc[-2] if len(frame) > 1 else latest
        price = _num(quote_raw.get("close"), latest.close)
        prev_close = _num(quote_raw.get("previous_close"), previous.close)
        change = _num(quote_raw.get("change"), price - prev_close)
        pct = _num(quote_raw.get("percent_change"), change / prev_close * 100 if prev_close else 0)
        quote = {
            "price": price, "open": _num(quote_raw.get("open"), latest.open),
            "high": _num(quote_raw.get("high"), latest.high),
            "low": _num(quote_raw.get("low"), latest.low),
            "previous_close": prev_close, "volume": int(_num(quote_raw.get("volume"), latest.volume)),
            "change": change, "percent_change": pct,
        }
        stats: dict[str, Any] = {}
        warning = ""
        try:
            stats = self._get("statistics", symbol=symbol).get("statistics", {})
        except Exception:
            warning = "基本面端点不可用，暂以 N/A 显示。"
        valuations = stats.get("valuations_metrics", {}) if isinstance(stats, dict) else {}
        financials = stats.get("financials", {}) if isinstance(stats, dict) else {}
        fundamentals = {
            "market_cap": _num_or_none(valuations.get("market_capitalization")),
            "pe": _num_or_none(valuations.get("trailing_pe")),
            "forward_pe": _num_or_none(valuations.get("forward_pe")),
            "peg": _num_or_none(valuations.get("peg_ratio")),
            "eps": _num_or_none(financials.get("diluted_eps_ttm")),
            "beta": _num_or_none(valuations.get("beta")),
            "week52_high": _num_or_none(stats.get("stock_price_summary", {}).get("fifty_two_week", {}).get("high")),
            "week52_low": _num_or_none(stats.get("stock_price_summary", {}).get("fifty_two_week", {}).get("low")),
        }
        meta = raw.get("meta", {})
        as_of = str(quote_raw.get("datetime") or frame.index[-1])
        exchange = meta.get("exchange", "US")
        return MarketPacket(
            symbol=symbol, frame=frame, quote=quote, fundamentals=fundamentals,
            source=f"Twelve Data · {exchange}", as_of=as_of, mode="live", warning=warning,
        )


def _num(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def _num_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    data["ma20"] = data.close.rolling(20, min_periods=1).mean()
    data["ma50"] = data.close.rolling(50, min_periods=1).mean()
    delta = data.close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = -delta.clip(upper=0).ewm(alpha=1 / 14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    data["rsi"] = (100 - 100 / (1 + rs)).fillna(50).clip(0, 100)
    ema12 = data.close.ewm(span=12, adjust=False).mean()
    ema26 = data.close.ewm(span=26, adjust=False).mean()
    data["macd"] = ema12 - ema26
    data["macd_signal"] = data.macd.ewm(span=9, adjust=False).mean()
    data["macd_hist"] = data.macd - data.macd_signal
    data["volume_avg20"] = data.volume.rolling(20, min_periods=1).mean()
    return data


def load_packet(symbol: str, range_key: str, api_key: str = "", demo: bool = False) -> MarketPacket:
    if demo or not api_key:
        return build_demo_packet(symbol, range_key)
    return TwelveDataProvider(api_key).packet(symbol, range_key)


def demo_watchlist() -> pd.DataFrame:
    rows = []
    for symbol, name in STOCKS.items():
        packet = build_demo_packet(symbol, "1M")
        rows.append({"代码": symbol, "名称": name, "最新价": packet.quote["price"],
                     "涨跌幅%": packet.quote["percent_change"], "状态": "模拟"})
    return pd.DataFrame(rows)
