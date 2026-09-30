"""Configuration shared by the dashboard, data layer and bot engine."""

STOCKS = {
    "NVDA": "英伟达",
    "INTC": "英特尔",
    "MSFT": "微软",
    "GOOG": "谷歌",
    "LRCX": "泛林集团",
    "ENTG": "英格特",
    "C": "花旗集团",
    "FLEX": "伟创力",
    "GE": "GE 航天航空",
    "EUV": "Corgi 微影与半导体光子",
}

RANGE_CONFIG = {
    "1D": {"interval": "5min", "outputsize": 78, "label": "当日 · 5分钟"},
    "5D": {"interval": "15min", "outputsize": 130, "label": "5日 · 15分钟"},
    "1M": {"interval": "1day", "outputsize": 35, "label": "1月 · 日线"},
    "3M": {"interval": "1day", "outputsize": 90, "label": "3月 · 日线"},
    "6M": {"interval": "1day", "outputsize": 180, "label": "6月 · 日线"},
    "1Y": {"interval": "1day", "outputsize": 365, "label": "1年 · 日线"},
}

ACCENT = "#27e0a3"
RED = "#ff5470"
GOLD = "#f6c85f"
BLUE = "#65a9ff"
PURPLE = "#a68cff"
BG = "#071017"
PANEL = "#0d1922"
MUTED = "#83919d"

