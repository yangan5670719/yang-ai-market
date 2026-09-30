# AI Market Lab

一个用于学习 AI 应用的数据驱动美股研究案例。它展示完整链路：

`行情采集 → 指标计算 → 信号识别 → AI解释 → 自动化调度 → 通知`

## 已完成

- 10只股票的终端式观察列表
- 1D / 5D / 1M / 3M / 6M / 1Y 多周期K线
- 成交量、MA20、MA50、RSI、MACD
- OHLC、涨跌幅和基本面快照
- 透明的 0–100 技术信号评分
- BOT事件流和规则解释
- 可选 OpenAI Responses API 模型解读
- Twelve Data 正规行情接口
- 数据源、模式与更新时间标识
- API失败后的明确降级，不用过期数据冒充实时行情

## 运行

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

首次运行默认进入 **SIMULATED 教学演示模式**，无需任何密钥。模拟行情只用于展示数据流，页面会持续显示醒目标识。

## 切换到真实行情

1. 注册 Twelve Data 并创建 API Key。
2. 复制 `.streamlit/secrets.toml.example` 为 `.streamlit/secrets.toml`。
3. 配置：

```toml
demo_mode = false
twelve_data_api_key = "你的密钥"
```

不要把真实密钥提交到 GitHub。项目已经在 `.gitignore` 中排除该文件。

免费行情额度有限，因此真实模式下观察列表按点击顺序逐只更新，并保留状态。页面不会把尚未扫描的数据伪装成实时价格。

## 启用真实 AI 解读

在 `.streamlit/secrets.toml` 继续配置：

```toml
openai_api_key = "你的密钥"
openai_model = "gpt-6-astra"
```

没有模型密钥时，系统使用完全透明的规则引擎，仍可展示信号、风险、支撑和压力。配置后，“AI BOT”页会显示模型解读按钮。模型调用遵循官方 Responses API，并只接收当前页面已经展示的结构化指标。

## 文件结构

- `streamlit_app.py`：终端界面、图表与交互
- `market_data.py`：模拟数据、Twelve Data适配器和指标计算
- `ai_engine.py`：可解释评分、事件流和模型调用
- `config.py`：股票列表、周期和主题配置
- `tests/test_core.py`：数据与评分的核心自动检查

## 数据原则

- 模拟、延迟与实时数据必须明确区分。
- 所有技术指标使用同一组已标明来源的OHLCV计算。
- 单个API失败不得拖垮整个页面。
- 缺失字段显示 `N/A`。
- AI没有收到新闻内容时不得生成新闻事实。
- 本项目用于学习AI应用与自动化，不构成投资建议。

## 后续学习阶段

1. 验证三个真实股票与六个周期的数据一致性。
2. 将API密钥迁移到部署平台的Secret管理。
3. 用n8n或定时任务执行后台扫描。
4. 保存信号历史并接入Telegram或邮件通知。
5. 部署到稳定托管环境，摆脱Codespaces临时预览地址。

