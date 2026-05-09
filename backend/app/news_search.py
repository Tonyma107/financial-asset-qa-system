import os
from pathlib import Path

import requests
from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")


def search_news(query: str, max_results: int = 3) -> str:
    """
    搜索与股票事件相关的新闻摘要。

    设计：
    - 有 TAVILY_API_KEY：调用 Tavily Search API
    - 无 TAVILY_API_KEY：明确说明新闻搜索未配置
    - 搜索失败：返回友好提示，不暴露完整内部错误
    """

    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        return "新闻搜索未配置（TAVILY_API_KEY 未设置），无法获取相关新闻。事件原因分析将仅基于量价数据。"

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
                "include_answer": False,
            },
            timeout=8,
        )

        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])

        if not results:
            return "未找到相关新闻。事件原因分析将仅基于量价数据。"

        summaries = []

        for item in results:
            title = item.get("title", "Untitled")
            content = item.get("content", "")
            url = item.get("url", "")

            content = content[:220].replace("\n", " ")

            summaries.append(
                f"- 标题：{title}\n"
                f"  摘要：{content}\n"
                f"  来源：{url}"
            )

        return "\n".join(summaries)

    except Exception as e:
        print(f"[NewsSearch] failed: {e}")
        return "新闻搜索暂时不可用。事件原因分析将仅基于量价数据。"