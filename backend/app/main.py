from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.market_data import build_market_answer, get_market_summary, sanitize_provider_error
from app.query_router import QueryRoute, classify_query
from app.rag import build_rag_answer, build_rag_index, retrieve_finance_docs
from app.schemas import ChatRequest, ChatResponse
from app.ticker_resolver import resolve_ticker

from app.event_analysis import analyze_event_movement, build_event_answer

from app.llm import (
    generate_event_answer_with_llm,
    generate_market_answer_with_llm,
    generate_rag_answer_with_llm,
)
from app.news_search import search_news

def is_prediction_question(question: str) -> bool:
    q = question.lower()

    prediction_keywords = [
        "预测",
        "明天",
        "未来",
        "下周",
        "下个月",
        "会涨",
        "会跌",
        "目标价",
        "target price",
        "forecast",
        "predict",
        "prediction",
        "tomorrow",
        "future",
    ]

    return any(keyword in q for keyword in prediction_keywords)

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
            fallback_answer = build_market_answer(request.question, market)

            answer = generate_market_answer_with_llm(
                question=request.question,
                market_data=market,
                fallback=fallback_answer,
            )

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
            safe_error = sanitize_provider_error(str(e))

            return ChatResponse(
                route=route.value,
                answer=(
                    "【查询失败】\n"
                    "系统未能成功获取行情数据。\n\n"
                    f"【错误信息】\n{safe_error}\n\n"
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
                    "error": safe_error,
                },
            )

    if route == QueryRoute.RAG_QA:
        try:
            retrieved_docs = retrieve_finance_docs(request.question, top_k=3)
            fallback_answer = build_rag_answer(request.question, retrieved_docs)

            answer = generate_rag_answer_with_llm(
                question=request.question,
                retrieved_docs=retrieved_docs,
                fallback=fallback_answer,
            )


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
            fallback_answer = build_event_answer(request.question, event)

            news_summary = ""

            if event.get("status") == "ok":
                news_query = (
                    f"{ticker} stock news {event.get('event_date')} "
                    f"{event.get('nearest_trading_date')} {request.question}"
                )
                news_summary = search_news(news_query, max_results=3)

                answer = generate_event_answer_with_llm(
                    question=request.question,
                    event_data=event,
                    news_summary=news_summary,
                    fallback=fallback_answer,
                )
            else:
                # For missing_date / out_of_range / insufficient_data,
                # keep deterministic fallback to avoid misleading LLM rewrites.
                answer = fallback_answer

            sources = []

            if event.get("data_source"):
                sources.append(event["data_source"])

            news_unavailable_phrases = [
                "新闻搜索未配置",
                "未找到相关新闻",
                "新闻搜索暂时不可用",
                "仅基于量价数据",
            ]

            if news_summary and not any(
                phrase in news_summary for phrase in news_unavailable_phrases
            ):
                sources.append("News Search")

            return ChatResponse(
                route=route.value,
                answer=answer,
                sources=sources,
                data={
                    "original_question": request.question,
                    "detected_route": route.value,
                    "detected_ticker": ticker,
                    "event": event,
                    "news_summary": news_summary,
                },
            )
        
        except Exception as e:
            safe_error = sanitize_provider_error(str(e))

            return ChatResponse(
                route=route.value,
                answer=(
                    "【事件分析失败】\n"
                    "系统未能成功完成事件分析。\n\n"
                    f"【错误信息】\n{safe_error}\n\n"
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
                    "error": safe_error,
                },
            )
        

    # --- 新插入的 EVENT_ANALYSIS 逻辑结束 ---
    if route == QueryRoute.GENERAL and is_prediction_question(request.question):
        return ChatResponse(
            route=route.value,
            answer=(
                "【无法提供预测】\n"
                "本系统不预测未来股价，也不提供买卖建议。\n\n"
                "【可以提供的替代分析】\n"
                "- 查询最近 7 天或 30 天历史走势\n"
                "- 计算历史涨跌幅和成交量变化\n"
                "- 分析某个已发生日期的异常波动\n"
                "- 解释金融指标或财报概念\n\n"
                "你可以这样问：\n"
                "- NVDA 最近 7 天涨跌情况如何？\n"
                "- 英伟达为何上周五大涨？\n"
                "- 什么是市盈率？"
            ),
            sources=[],
            data={
                "original_question": request.question,
                "detected_route": route.value,
                "reason": "prediction_not_supported",
            },
        )
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