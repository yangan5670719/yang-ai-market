from __future__ import annotations

from datetime import datetime
import html
import os

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from ai_engine import analyze, event_feed, llm_narrative, rule_narrative
from config import ACCENT, BG, BLUE, GOLD, MUTED, PANEL, PURPLE, RANGE_CONFIG, RED, STOCKS
from market_data import MarketDataError, demo_watchlist, load_packet


st.set_page_config(page_title="AI Market Lab", page_icon="◈", layout="wide", initial_sidebar_state="expanded")


def secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, os.getenv(name.upper(), default)))
    except Exception:
        return str(os.getenv(name.upper(), default))


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');
        :root {{ --bg:{BG}; --panel:{PANEL}; --accent:{ACCENT}; --red:{RED}; --muted:{MUTED}; }}
        .stApp {{ background: radial-gradient(circle at 72% -10%, #102c32 0, {BG} 38%); color:#eef6f5; }}
        [data-testid="stSidebar"] {{ background:#071017; border-right:1px solid #18303b; }}
        [data-testid="stSidebar"] > div {{ padding-top:1.2rem; }}
        .block-container {{ max-width:1640px; padding-top:1.25rem; padding-bottom:3rem; }}
        html, body, [class*="css"] {{ font-family:Inter, sans-serif; }}
        h1,h2,h3 {{ letter-spacing:-.035em; }}
        .mono {{ font-family:'JetBrains Mono',monospace; }}
        .eyebrow {{ color:{ACCENT}; font:600 11px 'JetBrains Mono'; letter-spacing:.16em; text-transform:uppercase; }}
        .hero {{ display:flex; justify-content:space-between; align-items:flex-end; padding:8px 0 22px; }}
        .hero h1 {{ font-size:38px; margin:6px 0 2px; }}
        .hero p {{ color:#91a1aa; margin:0; }}
        .status {{ padding:9px 13px; border:1px solid #21414d; border-radius:12px; background:#0a1820; color:#b9c7cc; font-size:12px; }}
        .live-dot {{ display:inline-block;width:7px;height:7px;border-radius:50%;background:{ACCENT};box-shadow:0 0 14px {ACCENT};margin-right:7px; }}
        .demo-dot {{ display:inline-block;width:7px;height:7px;border-radius:50%;background:{GOLD};box-shadow:0 0 14px {GOLD};margin-right:7px; }}
        .metric-card {{ min-height:112px; padding:17px 18px; background:linear-gradient(145deg,#0e1b24,#0a151d); border:1px solid #1b303b; border-radius:14px; }}
        .metric-label {{ color:#71828d; font-size:11px; letter-spacing:.08em; text-transform:uppercase; }}
        .metric-value {{ color:#f1f8f7; font:600 26px 'JetBrains Mono'; margin-top:14px; white-space:nowrap; }}
        .metric-delta {{ font:600 12px 'JetBrains Mono'; margin-top:8px; }}
        .panel {{ background:linear-gradient(145deg,#0d1922,#09131a);border:1px solid #1b303b;border-radius:16px;padding:19px; }}
        .signal {{ display:flex;gap:18px;align-items:center;padding:18px;border-radius:14px;background:#0a171e;border:1px solid #1a323d; }}
        .score {{ font:700 34px 'JetBrains Mono'; }}
        .event {{ border-left:2px solid {ACCENT};padding:8px 0 8px 14px;margin:7px 0;color:#c4d0d3;font-size:13px; }}
        .event time {{ color:#61737e;font:11px 'JetBrains Mono';margin-right:10px; }}
        .source-pill {{ display:inline-block;padding:5px 9px;border-radius:99px;border:1px solid #28434d;background:#0a1820;color:#9eb0b7;font:11px 'JetBrains Mono';margin:3px 5px 3px 0; }}
        .warning {{ border:1px solid #6b5721;background:#201b0b;color:#f6d87b;border-radius:12px;padding:11px 14px;font-size:12px; }}
        div[data-testid="stButton"] button {{ border-radius:10px;border:1px solid #23404c;background:#0c1b23;color:#c8d5d8;font-weight:600; }}
        div[data-testid="stButton"] button:hover {{ border-color:{ACCENT};color:{ACCENT}; }}
        div[data-testid="stDataFrame"] {{ border:1px solid #1b303b;border-radius:12px;overflow:hidden; }}
        div[data-testid="stTabs"] button {{ color:#8799a2; }}
        div[data-testid="stTabs"] button[aria-selected="true"] {{ color:{ACCENT}; }}
        #MainMenu, footer {{ visibility:hidden; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def money(value: object, compact: bool = False) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    number = float(value)
    if compact:
        for scale, suffix in [(1e12, "T"), (1e9, "B"), (1e6, "M")]:
            if abs(number) >= scale:
                return f"${number / scale:,.2f}{suffix}"
    return f"${number:,.2f}"


def number(value: object, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):,.2f}{suffix}"


def metric_card(label: str, value: str, delta: str = "", positive: bool | None = None) -> None:
    color = MUTED if positive is None else ACCENT if positive else RED
    delta_html = f'<div class="metric-delta" style="color:{color}">{html.escape(delta)}</div>' if delta else ""
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{html.escape(label)}</div>'
        f'<div class="metric-value">{html.escape(value)}</div>{delta_html}</div>',
        unsafe_allow_html=True,
    )


def market_chart(frame: pd.DataFrame, symbol: str) -> go.Figure:
    colors = [ACCENT if c >= o else RED for o, c in zip(frame.open, frame.close)]
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.035,
        row_heights=[0.56, 0.16, 0.14, 0.14],
    )
    fig.add_trace(
        go.Candlestick(
            x=frame.index, open=frame.open, high=frame.high, low=frame.low, close=frame.close,
            name=symbol, increasing_line_color=ACCENT, decreasing_line_color=RED,
            increasing_fillcolor="#0e6a55", decreasing_fillcolor="#743040",
        ), row=1, col=1,
    )
    fig.add_trace(go.Scatter(x=frame.index, y=frame.ma20, name="MA20", line=dict(color=GOLD, width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=frame.index, y=frame.ma50, name="MA50", line=dict(color=BLUE, width=1.5)), row=1, col=1)
    fig.add_trace(go.Bar(x=frame.index, y=frame.volume, name="成交量", marker_color=colors, opacity=.78), row=2, col=1)
    fig.add_trace(go.Scatter(x=frame.index, y=frame.rsi, name="RSI(14)", line=dict(color=PURPLE, width=1.7)), row=3, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="#596771", row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="#596771", row=3, col=1)
    hist_colors = [ACCENT if value >= 0 else RED for value in frame.macd_hist]
    fig.add_trace(go.Bar(x=frame.index, y=frame.macd_hist, name="MACD柱", marker_color=hist_colors), row=4, col=1)
    fig.add_trace(go.Scatter(x=frame.index, y=frame.macd, name="MACD", line=dict(color=BLUE, width=1.4)), row=4, col=1)
    fig.add_trace(go.Scatter(x=frame.index, y=frame.macd_signal, name="Signal", line=dict(color=GOLD, width=1.2)), row=4, col=1)
    fig.update_layout(
        height=790, margin=dict(l=8, r=12, t=35, b=8), paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#82939c", family="Inter"),
        hovermode="x unified", xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.02, x=0, bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(showgrid=False, linecolor="#20313a", zeroline=False)
    fig.update_yaxes(gridcolor="#162832", zeroline=False, side="right")
    fig.update_yaxes(range=[0, 100], row=3, col=1)
    return fig


def update_watchlist(symbol: str, name: str, packet, demo_mode: bool) -> pd.DataFrame:
    if "watchlist" not in st.session_state:
        if demo_mode:
            st.session_state.watchlist = demo_watchlist()
        else:
            st.session_state.watchlist = pd.DataFrame(
                [{"代码": ticker, "名称": company, "最新价": None, "涨跌幅%": None, "状态": "等待扫描"}
                 for ticker, company in STOCKS.items()]
            )
    table = st.session_state.watchlist.copy()
    idx = table.index[table["代码"] == symbol]
    if len(idx):
        table.loc[idx, ["最新价", "涨跌幅%", "状态"]] = [
            packet.quote["price"], packet.quote["percent_change"], "模拟" if demo_mode else "已更新"
        ]
    st.session_state.watchlist = table
    return table


inject_css()

td_key = secret("twelve_data_api_key")
openai_key = secret("openai_api_key")
openai_model = secret("openai_model", "gpt-6-astra")
configured_demo = secret("demo_mode", "true").lower() in {"1", "true", "yes", "on"}
demo_mode = configured_demo or not td_key

if "symbol" not in st.session_state:
    st.session_state.symbol = "NVDA"
if "range" not in st.session_state:
    st.session_state.range = "3M"

with st.sidebar:
    st.markdown('<div class="eyebrow">AI MARKET LAB</div>', unsafe_allow_html=True)
    st.markdown("## 自动化研究终端")
    st.caption("观察 → 计算 → 解释 → 记录")
    if demo_mode:
        st.markdown('<div class="warning">教学演示模式<br>当前所有行情均为模拟数据</div>', unsafe_allow_html=True)
    else:
        st.success("LIVE DATA · Twelve Data")
    st.markdown("#### 观察列表")
    for ticker, company in STOCKS.items():
        if st.button(f"{ticker}  ·  {company}", key=f"stock_{ticker}", use_container_width=True,
                     type="primary" if ticker == st.session_state.symbol else "secondary"):
            st.session_state.symbol = ticker
            st.rerun()
    st.divider()
    refresh = st.button("↻ 立即扫描", use_container_width=True)
    auto_refresh = st.toggle("自动扫描", value=False)
    interval = st.select_slider("扫描间隔", options=[1, 5, 15, 30, 60], value=5, format_func=lambda x: f"{x} 分钟")
    st.caption("自动扫描将在部署阶段接入后台调度；当前按钮用于学习数据流。")

symbol = st.session_state.symbol
name = STOCKS[symbol]

try:
    packet = load_packet(symbol, st.session_state.range, td_key, demo=demo_mode)
except Exception as exc:
    st.error(f"行情源请求失败：{exc}")
    st.info("系统已切换到明确标注的演示数据，页面不会伪装成实时行情。")
    packet = load_packet(symbol, st.session_state.range, demo=True)
    demo_mode = True

report = analyze(packet.frame)
watchlist = update_watchlist(symbol, name, packet, demo_mode)

mode_dot = "demo-dot" if demo_mode else "live-dot"
mode_text = "SIMULATED" if demo_mode else "LIVE"
st.markdown(
    f'<div class="hero"><div><div class="eyebrow">US EQUITIES · INTELLIGENCE DESK</div>'
    f'<h1>{symbol} <span style="color:#82939c;font-weight:500">{html.escape(name)}</span></h1>'
    f'<p>多周期行情、技术指标与可解释 AI 信号</p></div>'
    f'<div class="status"><span class="{mode_dot}"></span>{mode_text} &nbsp;·&nbsp; {html.escape(packet.source)}<br>'
    f'<span class="mono" style="color:#637681">AS OF {html.escape(packet.as_of[:19])}</span></div></div>',
    unsafe_allow_html=True,
)

if packet.warning:
    st.warning(packet.warning)

q = packet.quote
cols = st.columns(6)
with cols[0]: metric_card("最新价", money(q["price"]), f"{q['change']:+.2f}  {q['percent_change']:+.2f}%", q["change"] >= 0)
with cols[1]: metric_card("开盘", money(q["open"]))
with cols[2]: metric_card("最高", money(q["high"]))
with cols[3]: metric_card("最低", money(q["low"]))
with cols[4]: metric_card("昨收", money(q["previous_close"]))
with cols[5]: metric_card("成交量", f"{int(q['volume']):,}")

tabs = st.tabs(["总览", "AI BOT", "观察列表", "自动化", "数据说明"])

with tabs[0]:
    st.markdown("### 价格走势 · 技术指标")
    range_cols = st.columns(6)
    for col, key in zip(range_cols, RANGE_CONFIG):
        with col:
            if st.button(key, key=f"range_{key}", use_container_width=True,
                         type="primary" if key == st.session_state.range else "secondary"):
                st.session_state.range = key
                st.rerun()
    st.caption(RANGE_CONFIG[st.session_state.range]["label"])
    st.plotly_chart(market_chart(packet.frame, symbol), use_container_width=True, config={"displaylogo": False})

    st.markdown("### 基本面快照")
    f = packet.fundamentals
    basic_cols = st.columns(4)
    items = [
        ("市值", money(f.get("market_cap"), compact=True)), ("尾随 PE", number(f.get("pe"))),
        ("Forward PE", number(f.get("forward_pe"))), ("PEG", number(f.get("peg"))),
        ("EPS", money(f.get("eps"))), ("Beta", number(f.get("beta"))),
        ("52周高", money(f.get("week52_high"))), ("52周低", money(f.get("week52_low"))),
    ]
    for index, (label, value) in enumerate(items):
        with basic_cols[index % 4]:
            metric_card(label, value)

with tabs[1]:
    left, right = st.columns([1.12, .88], gap="large")
    with left:
        st.markdown("### BOT 信号引擎")
        st.markdown(
            f'<div class="signal"><div><div class="eyebrow">COMPOSITE SCORE</div>'
            f'<div class="score" style="color:{report.color}">{report.score}</div></div>'
            f'<div><div style="font-size:22px;font-weight:700;color:{report.color}">{report.label}</div>'
            f'<div style="color:#7f929b;margin-top:5px">基于 MA、RSI、MACD 与成交量的透明规则评分</div></div></div>',
            unsafe_allow_html=True,
        )
        st.markdown("#### 自动解读")
        if "analysis_text" not in st.session_state or st.session_state.get("analysis_symbol") != symbol:
            st.session_state.analysis_text = rule_narrative(symbol, report)
            st.session_state.analysis_symbol = symbol
        if openai_key:
            if st.button("✦ 使用模型重新解读", type="primary"):
                with st.spinner("模型正在分析结构化行情数据…"):
                    try:
                        st.session_state.analysis_text = llm_narrative(symbol, q, report, openai_key, openai_model)
                    except Exception as exc:
                        st.error(f"模型调用失败，继续显示规则分析：{exc}")
        else:
            st.caption("当前为规则分析。配置 OPENAI_API_KEY 后可启用真实模型解读。")
        st.markdown(st.session_state.analysis_text)
    with right:
        st.markdown("### 实时事件流")
        events = event_feed(symbol, packet.frame, report)
        for item in events:
            st.markdown(
                f'<div class="event"><time>{item["time"]}</time><b>{html.escape(item["level"])}</b>'
                f' · {html.escape(item["text"])}</div>', unsafe_allow_html=True,
            )
        st.markdown("### 自动化状态")
        metric_card("扫描器", "READY" if auto_refresh else "PAUSED", f"间隔 {interval} 分钟", auto_refresh)
        metric_card("数据质量", "SIMULATED" if demo_mode else "VERIFIED", packet.source, not demo_mode)

with tabs[2]:
    st.markdown("### Watchlist · 扫描状态")
    display = watchlist.copy()
    display["最新价"] = display["最新价"].map(lambda x: "N/A" if pd.isna(x) else f"${float(x):,.2f}")
    display["涨跌幅%"] = display["涨跌幅%"].map(lambda x: "N/A" if pd.isna(x) else f"{float(x):+.2f}%")
    st.dataframe(display, use_container_width=True, hide_index=True)
    st.caption("免费行情额度有限时，BOT 会按队列逐只扫描并记录每条数据的更新时间。")

with tabs[3]:
    st.markdown("### 自动化流水线")
    st.markdown(
        """
        <div class="panel mono" style="line-height:2.1">
        ① 定时触发 &nbsp;→&nbsp; ② 拉取授权行情 &nbsp;→&nbsp; ③ 计算指标<br>
        ④ 检测异动 &nbsp;→&nbsp; ⑤ AI生成解释 &nbsp;→&nbsp; ⑥ 保存与通知
        </div>
        """, unsafe_allow_html=True,
    )
    st.info("当前学习阶段：前台扫描器已完成。后台定时任务与消息通知将在数据源验证后接入。")
    checklist = pd.DataFrame([
        ["行情采集", "完成", packet.source], ["指标计算", "完成", "MA / RSI / MACD / Volume"],
        ["规则信号", "完成", f"{report.label} · {report.score}"],
        ["模型解读", "就绪" if openai_key else "待配置", openai_model if openai_key else "需要模型密钥"],
        ["后台调度", "下一阶段", "n8n / 定时任务"], ["主动通知", "下一阶段", "Telegram / Email"],
    ], columns=["模块", "状态", "说明"])
    st.dataframe(checklist, use_container_width=True, hide_index=True)

with tabs[4]:
    st.markdown("### 数据来源与可信度")
    st.markdown(f'<span class="source-pill">SOURCE {html.escape(packet.source)}</span>'
                f'<span class="source-pill">MODE {mode_text}</span>'
                f'<span class="source-pill">UPDATED {html.escape(packet.as_of[:19])}</span>', unsafe_allow_html=True)
    if demo_mode:
        st.error("当前是演示模式：价格、K线、基本面和Watchlist全部为模拟数据。它只用于展示数据流与AI工作方式。")
    else:
        st.success("当前选中股票的报价和K线来自 Twelve Data API。页面会保留来源与时间戳。")
    st.markdown(
        """
        **可信度规则**

        - 模拟数据永远显示黄色标识，不能伪装成实时行情。
        - API失败时显示错误并明确降级，不复用过期数据冒充最新行情。
        - 技术指标只基于页面标明的同一组OHLCV数据计算。
        - AI只能解释传入的结构化数据；没有新闻输入时不得编造新闻。
        - 本项目用于学习AI数据流与自动化，不提供投资建议。
        """
    )

