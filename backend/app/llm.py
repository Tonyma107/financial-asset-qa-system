import json
import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI

from app.prompts import (
    EVENT_ANALYSIS_PROMPT,
    MARKET_ANSWER_PROMPT,
    RAG_ANSWER_PROMPT,
)


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")


def call_llm(prompt: str, fallback: str = "") -> str:
    """
    调用 DeepSeek LLM 生成回答。

    设计：
    - 有 DEEPSEEK_API_KEY：调用 DeepSeek API
    - 无 DEEPSEEK_API_KEY：返回 fallback 模板回答
    - LLM 调用失败：返回 fallback，保证系统可运行
    """

    api_key = os.getenv("DEEPSEEK_API_KEY")

    if not api_key:
        return fallback if fallback else "[LLM not configured, using template fallback]"

    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个专业的金融分析助手。"
                        "你必须基于用户提供的数据和检索结果回答。"
                        "不得编造价格、成交量、日期、新闻、财报或政策。"
                        "如果证据不足，必须明确说明不确定性。"
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.2,
            max_tokens=1200,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"[LLM] call failed: {e}")
        return fallback if fallback else "【LLM 不可用】系统已降级为模板回答。"


def _to_json_text(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def _format_sources(sources: List[str]) -> str:
    if not sources:
        return "暂无来源"
    return "\n".join(f"- {source}" for source in sources)


def _average_volume_from_history(history: List[Dict[str, Any]]) -> float:
    volumes = []

    for row in history or []:
        value = row.get("Volume")
        if value is not None:
            try:
                volumes.append(float(value))
            except Exception:
                pass

    if not volumes:
        return 0.0

    return sum(volumes) / len(volumes)


def _volume_status_from_ratio(ratio: float | None) -> str:
    if ratio is None:
        return "无法判断"

    if ratio >= 1.2:
        return "放量"
    if ratio <= 0.8:
        return "缩量"
    return "持平"


def generate_market_answer_with_llm(
    question: str,
    market_data: Dict[str, Any],
    fallback: str,
) -> str:
    """
    使用 LLM 基于真实 market_data 生成结构化行情回答。
    如果没有 DeepSeek key，则使用 fallback。
    """

    history = market_data.get("history", [])
    avg_volume = _average_volume_from_history(history)

    prompt = MARKET_ANSWER_PROMPT.format(
        question=question,
        market_data=_to_json_text(market_data),
        start_price=market_data.get("start_close"),
        end_price=market_data.get("latest_close"),
        change_pct=market_data.get("change_pct"),
        high=market_data.get("high"),
        low=market_data.get("low"),
        avg_volume=round(avg_volume, 2),
        volume_status="仅展示均量，不判断放缩量",
        sources=_format_sources([market_data.get("data_source", "unknown")]),
    )

    return call_llm(prompt=prompt, fallback=fallback)


def generate_rag_answer_with_llm(
    question: str,
    retrieved_docs: List[Dict[str, Any]],
    fallback: str,
) -> str:
    """
    使用 LLM 基于 RAG retrieved_docs 生成金融知识回答。
    如果没有 DeepSeek key，则使用 fallback。
    """

    sources = sorted(
        {
            doc.get("source")
            for doc in retrieved_docs
            if doc.get("source")
        }
    )

    prompt = RAG_ANSWER_PROMPT.format(
        question=question,
        retrieved_docs=_to_json_text(retrieved_docs),
        sources=_format_sources(sources),
    )

    return call_llm(prompt=prompt, fallback=fallback)


def generate_event_answer_with_llm(
    question: str,
    event_data: Dict[str, Any],
    news_summary: str,
    fallback: str,
) -> str:
    """
    使用 LLM 基于事件行情数据和可选新闻摘要生成事件分析回答。
    如果没有 DeepSeek key，则使用 fallback。
    """

    volume_info = event_data.get("volume_analysis") or {}

    event_volume = volume_info.get("event_volume")
    avg_volume = volume_info.get("avg_volume_prior_10_trading_days")
    volume_ratio = volume_info.get("volume_ratio")

    volume_status = _volume_status_from_ratio(volume_ratio)

    sources = []
    if event_data.get("data_source"):
        sources.append(event_data["data_source"])

    if news_summary and "新闻搜索未配置" not in news_summary and "未找到相关新闻" not in news_summary:
        sources.append("News Search")

    prompt = EVENT_ANALYSIS_PROMPT.format(
        question=question,
        market_data=_to_json_text(event_data),
        news_summary=news_summary or "新闻搜索未配置或未返回相关新闻。",
        date=event_data.get("nearest_trading_date") or event_data.get("event_date"),
        daily_return=event_data.get("daily_change_pct"),
        volume=event_volume,
        avg_volume=avg_volume,
        volume_status=volume_status,
        sources=_format_sources(sources),
    )

    return call_llm(prompt=prompt, fallback=fallback)