# Financial Asset QA System 金融资产问答系统

这是一个基于 **全栈 Web + 金融行情 API + RAG 知识库 + 结构化回答生成** 的金融资产问答系统。

项目目标不是做一个简单的 LLM 套壳，而是实现一个能够根据问题类型自动选择工具的金融问答系统：

- 行情类问题：调用外部行情 API 获取真实数据
- 金融知识类问题：通过本地金融知识库和 Chroma 向量检索回答
- 事件分析类问题：结合历史行情、涨跌幅和成交量进行分析
- 所有回答尽量区分“客观数据”和“分析性描述”，减少 hallucination

---

## 1. 项目可以做什么？

系统目前支持以下类型的问题。

### 1.1 资产行情问答

示例：

```text
BABA 最近 7 天涨跌情况如何？
AAPL 最近 7 天涨跌情况
腾讯股价多少？
谷歌近期表现如何？
```

系统会自动完成：

1. 识别公司名称或股票代码
2. 调用行情数据 API
3. 获取历史价格数据
4. 计算涨跌额和涨跌幅
5. 判断趋势：上涨 / 下跌 / 震荡
6. 返回结构化回答和数据来源

示例回答结构：

```text
【结论】
【客观数据】
【趋势分析】
【数据来源】
【风险提示】
```

---

### 1.2 事件原因分析

示例：

```text
阿里巴巴为何 5 月 6 日大涨？
苹果为何昨天大涨？
英伟达为何上周大涨？
特斯拉 4 月 30 日为什么跌了？
苹果为何 2020 年 3 月 1 日大跌？
```

系统会自动完成：

1. 识别股票代码
2. 解析日期
3. 查询对应交易日行情
4. 计算当日涨跌幅
5. 对比当日成交量和前 10 个交易日平均成交量
6. 判断是否真的“大涨”或“大跌”
7. 输出不确定性说明，避免编造新闻原因

如果用户的问题假设不成立，例如：

```text
阿里巴巴为何 1 月 15 日大涨？
```

但数据显示当天只上涨了 0.61%，系统会说明这是“小幅波动/震荡”，而不是顺着用户问题编造“大涨原因”。

---

### 1.3 金融知识 RAG 问答

示例：

```text
什么是市盈率？
收入和净利润的区别是什么？
现金流为什么重要？
资产负债表是什么？
```

系统不会完全依赖模型自由生成，而是先从本地金融知识库检索相关文档，再生成回答。

当前知识库包括：

```text
backend/docs/
├── pe_ratio.md
├── revenue_vs_net_income.md
├── cash_flow.md
└── balance_sheet.md
```

RAG 流程：

1. 读取 Markdown 文档
2. 文档分块
3. 存入 Chroma 向量数据库
4. 根据用户问题检索相关 chunk
5. 使用关键词 rerank 优化中文金融概念检索
6. 返回带来源的结构化答案

---

## 2. 系统架构

```text
User
 ↓
React / Vite Frontend
 ↓
FastAPI Backend
 ↓
Query Router
 ├── market_data
 │    ├── Ticker Resolver
 │    ├── Alpha Vantage API
 │    ├── yfinance fallback
 │    └── Local cache fallback
 │
 ├── rag_qa
 │    ├── Markdown Knowledge Base
 │    ├── Text Chunking
 │    ├── Chroma Vector Database
 │    └── Keyword Reranking
 │
 ├── event_analysis
 │    ├── Date Parser
 │    ├── Market Data Lookup
 │    ├── Daily Return Calculation
 │    ├── Volume Comparison
 │    └── Uncertainty Explanation
 │
 └── general
      └── Basic fallback response
 ↓
Structured Answer
```

---

## 3. 技术栈

### Frontend

- React
- Vite
- CSS

### Backend

- FastAPI
- Pydantic
- Python

### Market Data

- Alpha Vantage
- yfinance fallback
- Local cache fallback

### RAG

- ChromaDB
- Local Markdown knowledge base
- Custom chunking
- Vector retrieval
- Keyword reranking

### Answer Generation

当前版本主要使用结构化模板回答，优点是稳定、可控、可解释。

项目也预留了 LLM 扩展空间。后续可以接入 OpenAI、DeepSeek、Qwen 等模型，让 LLM 基于已经检索到的行情数据和 RAG 文档生成更自然的回答。

---

## 4. 项目结构

```text
financial-asset-qa-from-scratch/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── schemas.py
│   │   ├── query_router.py
│   │   ├── ticker_resolver.py
│   │   ├── market_data.py
│   │   ├── rag.py
│   │   └── event_analysis.py
│   │
│   ├── docs/
│   │   ├── pe_ratio.md
│   │   ├── revenue_vs_net_income.md
│   │   ├── cash_flow.md
│   │   └── balance_sheet.md
│   │
│   ├── requirements.txt
│   ├── .env.example
│   ├── cache/
│   └── chroma_db/
│
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── api.js
│       └── styles.css
│
├── .gitignore
└── README.md
```

---

## 5. 环境变量配置

项目需要 Alpha Vantage API Key。

在 `backend/` 目录下创建 `.env`：

```bash
cd backend
touch .env
```

写入：

```env
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key_here
```

注意：

真实 API Key 只能放在本地 `.env` 文件中，不要提交到 GitHub。

GitHub 中只应该保留：

```text
backend/.env.example
```

`.env.example` 示例：

```env
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key_here
```

---

## 6. 后端运行方式

进入后端目录：

```bash
cd backend
```

创建虚拟环境：

```bash
python3 -m venv .venv
```

激活虚拟环境：

```bash
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

启动 FastAPI：

```bash
uvicorn app.main:app --reload --port 8000
```

测试后端是否启动成功：

```bash
curl http://localhost:8000/api/health
```

预期返回：

```json
{
  "status": "ok",
  "message": "Financial Asset QA backend is running"
}
```

---

## 7. 构建 RAG 知识库

首次运行 RAG 功能前，需要构建 Chroma 向量索引：

```bash
curl -X POST http://localhost:8000/api/ingest
```

预期返回类似：

```json
{
  "inserted_chunks": 4,
  "files": [
    "balance_sheet.md",
    "cash_flow.md",
    "pe_ratio.md",
    "revenue_vs_net_income.md"
  ],
  "collection": "finance_knowledge"
}
```

---

## 8. 前端运行方式

打开另一个 terminal：

```bash
cd frontend
npm install
npm run dev
```

浏览器打开：

```text
http://localhost:5173
```

如果使用 Vite 显示的 Network URL，例如：

```text
http://10.20.63.7:5173
```

需要确认后端 `main.py` 的 CORS 设置允许这个 origin。

---

## 9. API 接口

### 9.1 Health Check

```text
GET /api/health
```

---

### 9.2 构建 RAG Index

```text
POST /api/ingest
```

---

### 9.3 Chat 接口

```text
POST /api/chat
```

请求示例：

```json
{
  "question": "BABA 最近 7 天涨跌情况如何？"
}
```

返回示例：

```json
{
  "route": "market_data",
  "answer": "...",
  "sources": ["Alpha Vantage TIME_SERIES_DAILY"],
  "data": {
    "detected_ticker": "BABA"
  }
}
```

---

## 10. Query Router 查询路由逻辑

系统会先判断用户问题类型，而不是把所有问题都交给模型自由回答。

### 10.1 Market Data

示例：

```text
阿里巴巴当前股价是多少？
BABA 最近 7 天涨跌情况如何？
腾讯股价多少？
谷歌近期表现如何？
```

路由：

```text
market_data
```

---

### 10.2 RAG QA

示例：

```text
什么是市盈率？
收入和净利润的区别是什么？
现金流为什么重要？
资产负债表是什么？
```

路由：

```text
rag_qa
```

---

### 10.3 Event Analysis

示例：

```text
阿里巴巴为何 5 月 6 日大涨？
苹果为何昨天大涨？
英伟达为何上周大涨？
特斯拉 4 月 30 日为什么跌了？
```

路由：

```text
event_analysis
```

---

### 10.4 General

示例：

```text
你好
```

路由：

```text
general
```

---

## 11. 股票代码识别

系统支持中文公司名、英文公司名和 ticker 识别。

当前支持示例：

```text
阿里巴巴 → BABA
特斯拉 → TSLA
苹果 → AAPL
英伟达 → NVDA
微软 → MSFT
亚马逊 → AMZN
谷歌 → GOOGL
腾讯 → TCEHY
台积电 → TSM
京东 → JD
拼多多 → PDD
百度 → BIDU
比亚迪 → BYDDY
小米 → XIACF
```

如果无法识别公司或 ticker，系统会提示用户输入更明确的股票代码或公司名称。

---

## 12. 日期解析能力

事件分析支持以下日期表达：

```text
今天
昨天
上周
上周五
1 月 15 日
2026 年 1 月 15 日
2026-01-15
2026/01/15
```

其中：

- “昨天”会转换为实际日期
- “上周五”会转换为上周五的实际日期
- “上周”在当前 demo 中默认使用上周五作为代表日期
- “2020 年 3 月 1 日”会正确解析为 2020-03-01

---

## 13. 数据范围保护

系统包含数据范围检查，避免严重错误。

例如用户问：

```text
苹果为何 2020 年 3 月 1 日大跌？
```

如果当前 Alpha Vantage compact 数据只覆盖最近一段时间，系统不会偷偷使用 2026 年的数据来回答 2020 年的问题。

系统会返回类似：

```text
系统无法查询该日期的行情数据，因此不会生成可能误导的结论。
```

这可以避免错误年份导致的 hallucination 风险。

---

## 14. 幻觉控制策略

本项目重点考虑了 hallucination control。

### 14.1 行情数据不由模型编造

股票价格、涨跌幅、最高价、最低价和成交量都来自外部行情 API。

当前主要使用：

```text
Alpha Vantage TIME_SERIES_DAILY
```

备用：

```text
yfinance
```

---

### 14.2 RAG 问答必须基于知识库

金融知识问答会先检索本地文档，而不是完全依赖模型记忆。

---

### 14.3 明确展示来源

回答中会展示数据来源，例如：

```text
Alpha Vantage TIME_SERIES_DAILY
Yahoo Finance via yfinance
pe_ratio.md
cash_flow.md
```

---

### 14.4 区分客观数据和分析描述

回答结构通常包含：

```text
【客观数据】
【趋势分析】
【可能影响因素分析】
【不确定性说明】
```

这样用户可以清楚区分事实数据和解释性分析。

---

### 14.5 不顺从错误前提

如果用户问：

```text
阿里巴巴为何 1 月 15 日大涨？
```

但数据表明当天并没有明显上涨，系统会明确说明当天只是小幅波动，而不是编造“大涨原因”。

---

### 14.6 数据范围不足时拒绝误导性回答

如果用户查询 2020 年，但当前数据源只提供近期数据，系统会说明数据范围不足，而不是错误使用当前年份的数据。

---

### 14.7 隐藏内部 API 原始错误

系统不会把 Alpha Vantage 的原始限速文本直接暴露给用户，而是转换成更友好的提示，例如：

```text
行情数据源暂时不可用，系统已尝试备用数据源。
```

---

## 15. 测试问题

### 15.1 行情类

```text
BABA 最近 7 天涨跌情况如何？
AAPL 最近 7 天涨跌情况
腾讯股价多少？
谷歌近期表现如何？
```

---

### 15.2 RAG 类

```text
什么是市盈率？
什么是现金流？
收入和净利润的区别是什么？
资产负债表是什么？
```

---

### 15.3 事件分析类

```text
阿里巴巴为何 5 月 6 日大涨？
苹果为何昨天大涨？
英伟达为何上周大涨？
特斯拉 4 月 30 日为什么跌了？
苹果为何 2020 年 3 月 1 日大跌？
```

---

## 16. 已修复的重要问题

### Bug 1：相对日期无法解析

原问题：

```text
苹果为何昨天大涨？
英伟达为何上周大涨？
```

之前系统无法识别日期。

修复后：

- 今天 → 当前日期
- 昨天 → 当前日期前一天
- 上周五 → 上周五实际日期
- 上周 → 默认使用上周五作为代表日期

---

### Bug 2：年份被忽略

原问题：

```text
苹果为何 2020 年 3 月 1 日大跌？
```

之前系统可能错误解析成当前年份，例如 2026 年。

修复后：

系统正确识别完整中文日期：

```text
2020 年 3 月 1 日 → 2020-03-01
```

并且如果该日期超出数据范围，系统会明确拒绝回答，不会错误映射到 2026 年。

---

### Bug 3：腾讯无法识别

原问题：

```text
腾讯股价多少？
```

之前无法识别 ticker。

修复后：

```text
腾讯 → TCEHY
```

同时补充了：

```text
台积电 → TSM
京东 → JD
拼多多 → PDD
百度 → BIDU
比亚迪 → BYDDY
小米 → XIACF
```

---

### Bug 4：Alpha Vantage 原始限速信息暴露

原问题：

系统会直接展示 Alpha Vantage 的英文原始限速信息。

修复后：

内部 provider error 会被转换成用户友好的提示，避免暴露冗长和不专业的 API 原始错误。

---

## 17. 当前限制

1. 当前项目不预测未来价格。
2. 当前项目不提供投资建议。
3. 新闻搜索暂未完整接入。
4. 事件原因分析目前主要基于价格和成交量，不直接判断真实因果。
5. Alpha Vantage 免费 API 有请求频率限制。
6. RAG 知识库规模较小，主要用于 demo。
7. 当前回答生成主要是模板化结构化回答，后续可以接入 LLM 做更自然的总结。

---

## 18. 后续优化方向

1. 接入 OpenAI / DeepSeek / Qwen 等 LLM。
2. 接入新闻搜索 API，例如 Tavily、SerpAPI 或 Bing Search。
3. 接入 SEC filing 或公司财报数据。
4. 扩充金融知识库。
5. 增加股票走势图可视化。
6. 增加单元测试，覆盖日期解析、ticker resolver 和 query router。
7. 加入更完善的本地缓存和 rate-limit control。
8. 使用 Docker Compose 实现一键启动。
9. 增加更多行情数据源 fallback。
10. 增加多轮对话上下文管理。

---

## 19. 注意事项

### 19.1 不要提交 API Key

不要提交：

```text
backend/.env
```

GitHub 里只保留：

```text
backend/.env.example
```

---

### 19.2 不要提交虚拟环境和依赖目录

不要提交：

```text
backend/.venv/
frontend/node_modules/
```

---

### 19.3 不要提交本地缓存

建议不要提交：

```text
backend/cache/
backend/chroma_db/
```

RAG index 可以通过接口重新构建：

```bash
curl -X POST http://localhost:8000/api/ingest
```

---

### 19.4 CORS 设置

如果前端使用：

```text
http://localhost:5173
```

后端 CORS 需要允许：

```text
http://localhost:5173
```

如果前端使用 Vite 的 Network URL，例如：

```text
http://10.20.63.7:5173
```

也需要把这个 origin 加入 FastAPI 的 CORS allow_origins。

---

## 20. 免责声明

本项目仅用于学习、技术展示和面试 demo。

本系统不构成：

- 投资建议
- 金融建议
- 交易建议
- 买卖推荐
- 未来价格预测

所有行情数据来自外部数据源，例如 Alpha Vantage 和 yfinance。数据的准确性、延迟和可用性取决于第三方数据服务。

系统会尽量通过行情 API、RAG 检索、数据来源展示和日期范围检查来减少 hallucination，但用户在做任何金融决策前，仍应参考官方财报、交易所数据、公司公告、SEC 文件或专业金融数据源。

---

## 21. Demo 视频建议流程

3 分钟 demo 可以这样录：

### 0:00 - 0:30 系统介绍

说明这是一个全栈金融资产问答系统，包含：

- React 前端
- FastAPI 后端
- Query Router
- Alpha Vantage / yfinance 行情数据
- Chroma RAG 知识库

---

### 0:30 - 1:10 行情问答

展示：

```text
BABA 最近 7 天涨跌情况如何？
```

说明：

系统调用外部行情 API，计算涨跌幅和趋势，不由模型自由生成价格。

---

### 1:10 - 1:50 RAG 问答

展示：

```text
什么是市盈率？
```

说明：

系统从本地金融知识库检索相关内容，并返回带来源的回答。

---

### 1:50 - 2:30 事件分析

展示：

```text
阿里巴巴为何 5 月 6 日大涨？
```

说明：

系统解析日期，计算单日涨跌幅，并对比成交量。

---

### 2:30 - 3:00 幻觉控制

展示：

```text
苹果为何 2020 年 3 月 1 日大跌？
```

说明：

如果日期超出当前数据范围，系统不会编造答案，也不会错误使用 2026 年数据。

---

## 22. 提交前检查

提交 GitHub 前建议运行：

```bash
cd backend
source .venv/bin/activate
python -m py_compile app/*.py
```

然后：

```bash
cd ../frontend
npm run build
```

再检查 git：

```bash
cd ..
git status
```

确认没有提交以下文件：

```text
backend/.env
backend/.venv/
frontend/node_modules/
backend/cache/
backend/chroma_db/
```

---

## 23. 总结

这个项目展示了一个金融资产问答系统从 0 到 1 的核心工程能力：

- 前后端分离
- FastAPI API 设计
- React 交互界面
- 股票 ticker 识别
- 外部行情 API 集成
- RAG 知识库检索
- Query Router 查询路由
- 日期解析和边界处理
- 数据范围保护
- 幻觉控制
- 结构化金融回答生成

