from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.market_data import build_market_answer, get_market_summary
from app.query_router import QueryRoute, classify_query
from app.rag import build_rag_answer, build_rag_index, retrieve_finance_docs
from app.schemas import ChatRequest, ChatResponse
from app.ticker_resolver import resolve_ticker

from app.event_analysis import analyze_event_movement, build_event_answer


app = FastAPI(
    title="Financial Asset QA System",
    description="A full-stack financial asset question answering system with market data, RAG, and LLM structured responses.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://10.20.63.7:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "message": "Financial Asset QA backend is running",
    }

@app.post("/api/ingest")
def ingest_docs():
    return build_rag_index()



@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    route = classify_query(request.question)

    ticker = None
    if route in [QueryRoute.MARKET_DATA, QueryRoute.EVENT_ANALYSIS]:
        ticker = resolve_ticker(request.question)

    if route in [QueryRoute.MARKET_DATA, QueryRoute.EVENT_ANALYSIS] and ticker is None:
        answer = (
            f"我已经收到你的问题：{request.question}\n\n"
            f"当前 Query Router 判断这个问题类型是：{route.value}\n\n"
            "但是系统暂时没有识别出股票代码或公司名称。\n\n"
            "你可以尝试这样问：\n"
            "- BABA 最近 7 天涨跌情况如何？\n"
            "- 阿里巴巴当前股价是多少？\n"
            "- TSLA 最近 30 天走势如何？"
        )

        return ChatResponse(
            route=route.value,
            answer=answer,
            sources=[],
            data={
                "original_question": request.question,
                "detected_route": route.value,
                "detected_ticker": ticker,
            },
        )

    if route == QueryRoute.MARKET_DATA:
        try:
            market = get_market_summary(ticker=ticker, question=request.question)
            answer = build_market_answer(request.question, market)

            return ChatResponse(
                route=route.value,
                answer=answer,
                sources=[market["data_source"]],
                data={
                    "original_question": request.question,
                    "detected_route": route.value,
                    "detected_ticker": ticker,
                    "market": market,
                },
            )

        except Exception as e:
            return ChatResponse(
                route=route.value,
                answer=(
                    "【查询失败】\n"
                    "系统未能成功获取行情数据。\n\n"
                    f"【错误信息】\n{str(e)}\n\n"
                    "【建议】\n"
                    "- 稍后重试\n"
                    "- 尝试输入更明确的股票代码，例如 BABA、TSLA、AAPL\n"
                    "- 如果数据源持续失败，可以切换到其他行情 API"
                ),
                sources=[],
                data={
                    "original_question": request.question,
                    "detected_route": route.value,
                    "detected_ticker": ticker,
                    "error": str(e),
                },
            )

    if route == QueryRoute.RAG_QA:
        try:
            retrieved_docs = retrieve_finance_docs(request.question, top_k=3)
            answer = build_rag_answer(request.question, retrieved_docs)

            sources = sorted(
                {
                    doc["source"]
                    for doc in retrieved_docs
                    if doc.get("source")
                }
            )

            return ChatResponse(
                route=route.value,
                answer=answer,
                sources=sources,
                data={
                    "original_question": request.question,
                    "detected_route": route.value,
                    "retrieved_docs": retrieved_docs,
                },
            )

        except Exception as e:
            return ChatResponse(
                route=route.value,
                answer=(
                    "【RAG 查询失败】\n"
                    "系统未能成功检索本地金融知识库。\n\n"
                    f"【错误信息】\n{str(e)}\n\n"
                    "【建议】\n"
                    "- 请确认已经运行 POST /api/ingest\n"
                    "- 请确认 backend/docs/ 目录下存在 markdown 文档\n"
                    "- 请确认 Chroma 依赖安装成功"
                ),
                sources=[],
                data={
                    "original_question": request.question,
                    "detected_route": route.value,
                    "error": str(e),
                },
            )

    # --- 新插入的 EVENT_ANALYSIS 逻辑开始 ---
    if route == QueryRoute.EVENT_ANALYSIS:
        try:
            event = analyze_event_movement(ticker=ticker, question=request.question)
            answer = build_event_answer(request.question, event)

            sources = []
            if event.get("data_source"):
                sources.append(event["data_source"])

            return ChatResponse(
                route=route.value,
                answer=answer,
                sources=sources,
                data={
                    "original_question": request.question,
                    "detected_route": route.value,
                    "detected_ticker": ticker,
                    "event": event,
                },
            )

        except Exception as e:
            return ChatResponse(
                route=route.value,
                answer=(
                    "【事件分析失败】\n"
                    "系统未能成功完成事件分析。\n\n"
                    f"【错误信息】\n{str(e)}\n\n"
                    "【建议】\n"
                    "- 请确认问题中包含明确股票代码或公司名称\n"
                    "- 请确认问题中包含日期，例如 2026-01-15 或 1 月 15 日\n"
                    "- 如果行情数据源失败，可以稍后重试"
                ),
                sources=[],
                data={
                    "original_question": request.question,
                    "detected_route": route.value,
                    "detected_ticker": ticker,
                    "error": str(e),
                },
            )
    # --- 新插入的 EVENT_ANALYSIS 逻辑结束 ---

    # Fallback answer
    answer = (
        f"我已经收到你的问题：{request.question}\n\n"
        f"当前 Query Router 判断这个问题类型是：{route.value}\n"
    )

    if ticker:
        answer += f"\n系统识别出的股票代码是：{ticker}\n"

    answer += (
        "\n这个 route 的完整功能我们会在后续步骤实现。\n\n"
        "当前已经完成：\n"
        "- health check\n"
        "- query router\n"
        "- ticker resolver\n"
        "- market data API\n"
        "- event analysis API"
    )

    return ChatResponse(
        route=route.value,
        answer=answer,
        sources=[],
        data={
            "original_question": request.question,
            "detected_route": route.value,
            "detected_ticker": ticker,
        },
    )