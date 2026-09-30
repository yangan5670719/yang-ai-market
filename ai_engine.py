"""Transparent signal scoring plus optional LLM narrative generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any

import pandas as pd


@dataclass
class SignalReport:
    score: int
    label: str
    color: str
    signals: list[str]
    risks: list[str]
    support: float
    resistance: float


def analyze(frame: pd.DataFrame) -> SignalReport:
    latest = frame.iloc[-1]
    previous = frame.iloc[-2] if len(frame) > 1 else latest
    score = 50
    signals: list[str] = []
    risks: list[str] = []

    if latest.close > latest.ma20:
        score += 9; signals.append("价格位于 MA20 上方")
    else:
        score -= 9; signals.append("价格位于 MA20 下方")
    if latest.ma20 > latest.ma50:
        score += 11; signals.append("MA20 高于 MA50，中期结构偏多")
    else:
        score -= 11; signals.append("MA20 低于 MA50，中期结构偏弱")
    if latest.macd > latest.macd_signal:
        score += 8; signals.append("MACD 位于信号线上方")
    else:
        score -= 8; signals.append("MACD 位于信号线下方")
    if latest.rsi < 30:
        score += 4; risks.append("RSI 进入超卖区，反弹与继续下跌风险并存")
    elif latest.rsi > 70:
        score -= 4; risks.append("RSI 进入超买区，需防范动量回落")
    else:
        signals.append(f"RSI {latest.rsi:.1f}，动量处于中性区间")
    volume_ratio = latest.volume / latest.volume_avg20 if latest.volume_avg20 else 1
    if volume_ratio > 1.5:
        signals.append(f"成交量为20期均量的 {volume_ratio:.1f} 倍")
        score += 5 if latest.close > previous.close else -5
    change = (latest.close / previous.close - 1) * 100 if previous.close else 0
    if abs(change) > 3:
        risks.append(f"最近一期波动达到 {change:+.1f}%")

    score = max(0, min(100, round(score)))
    label = "偏多" if score >= 62 else "偏空" if score <= 38 else "中性"
    color = "#27e0a3" if label == "偏多" else "#ff5470" if label == "偏空" else "#f6c85f"
    window = frame.tail(min(20, len(frame)))
    return SignalReport(
        score=score, label=label, color=color, signals=signals, risks=risks or ["未发现极端技术风险"],
        support=float(window.low.min()), resistance=float(window.high.max()),
    )


def rule_narrative(symbol: str, report: SignalReport) -> str:
    lead = {
        "偏多": "趋势与动量指标形成一定共振，但仍需等待价格确认。",
        "偏空": "当前技术结构承压，反弹前应先观察止跌信号。",
        "中性": "多空条件尚未形成一致方向，更适合等待突破。",
    }[report.label]
    return (
        f"**{symbol} · {report.label}（{report.score}/100）**\n\n{lead}\n\n"
        f"**主要依据**\n" + "\n".join(f"- {item}" for item in report.signals[:4]) +
        f"\n\n**关键区间**\n- 支撑参考：${report.support:,.2f}\n- 压力参考：${report.resistance:,.2f}\n\n"
        "**风险观察**\n" + "\n".join(f"- {item}" for item in report.risks[:3])
    )


def llm_narrative(symbol: str, quote: dict[str, Any], report: SignalReport,
                  api_key: str, model: str = "gpt-6-astra") -> str:
    """Use the OpenAI Responses API only when the learner supplies a key."""
    if not api_key:
        return rule_narrative(symbol, report)
    from openai import OpenAI

    payload = {
        "symbol": symbol, "quote": quote, "score": report.score, "label": report.label,
        "signals": report.signals, "risks": report.risks,
        "support": report.support, "resistance": report.resistance,
    }
    instructions = (
        "你是美股研究教学助手。仅根据给定JSON写中文分析，不补充未提供的新闻或事实。"
        "依次输出趋势、证据、风险、下一步观察条件；控制在350字内；明确这不是投资建议。"
    )
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=[
            {"role": "developer", "content": instructions},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
        ],
        store=False,
    )
    return response.output_text


def event_feed(symbol: str, frame: pd.DataFrame, report: SignalReport) -> list[dict[str, str]]:
    now = datetime.now().strftime("%H:%M")
    latest = frame.iloc[-1]
    events = [
        {"time": now, "level": report.label, "text": f"{symbol} 综合信号更新为 {report.label} · {report.score}/100"},
        {"time": now, "level": "观察", "text": f"RSI {latest.rsi:.1f}，MACD 柱 {latest.macd_hist:+.2f}"},
    ]
    if latest.volume > latest.volume_avg20 * 1.5:
        events.append({"time": now, "level": "异动", "text": f"{symbol} 出现显著放量"})
    return events

