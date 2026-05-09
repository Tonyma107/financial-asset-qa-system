from enum import Enum


class QueryRoute(str, Enum):
    MARKET_DATA = "market_data"
    RAG_QA = "rag_qa"
    EVENT_ANALYSIS = "event_analysis"
    GENERAL = "general"


def classify_query(question: str) -> QueryRoute:
    """
    Classify the user's question into one of the system routes.

    Important design:
    - Pure financial concept questions should go to RAG, even if they contain "为什么".
      Example: "现金流为什么重要？" -> rag_qa
    - Stock movement reason questions should go to event analysis.
      Example: "阿里巴巴为什么大涨？" -> event_analysis
    """

    q = question.lower().strip()

    rag_keywords = [
        "什么是",
        "区别",
        "市盈率",
        "pe",
        "p/e",
        "收入",
        "营收",
        "净利润",
        "资产负债表",
        "现金流",
        "财报",
        "eps",
        "revenue",
        "net income",
        "cash flow",
        "balance sheet",
    ]

    event_keywords = [
        "为什么",
        "为何",
        "原因",
        "大涨",
        "大跌",
        "暴涨",
        "暴跌",
        "why",
        "reason",
        "cause",
    ]

    market_keywords = [
        "股价",
        "价格",
        "当前",
        "现在",
        "涨跌",
        "走势",
        "最近",
        "7天",
        "7 天",
        "30天",
        "30 天",
        "price",
        "stock",
        "trend",
        "return",
    ]

    company_keywords = [
        "阿里巴巴",
        "阿里",
        "baba",
        "特斯拉",
        "tesla",
        "tsla",
        "苹果",
        "apple",
        "aapl",
        "英伟达",
        "nvidia",
        "nvda",
        "微软",
        "microsoft",
        "msft",
        "亚马逊",
        "amazon",
        "amzn",
        "谷歌",
        "google",
        "googl",
        "meta",
        "facebook",
        "腾讯",
        "腾讯控股",
        "tencent",
        "tcehy",
        "台积电",
        "tsmc",
        "tsm",
        "京东",
        "jd",
        "拼多多",
        "pdd",
        "百度",
        "baidu",
        "bidu",
        "比亚迪",
        "byd",
        "byddy",
        "小米",
        "xiaomi",
        "xiacf",
    ]

    has_rag_keyword = any(keyword in q for keyword in rag_keywords)
    has_event_keyword = any(keyword in q for keyword in event_keywords)
    has_market_keyword = any(keyword in q for keyword in market_keywords)
    has_company_keyword = any(keyword in q for keyword in company_keywords)

    # Case 1:
    # Stock movement reason analysis.
    # Example: "阿里巴巴为何 1 月 15 日大涨？"
    if has_event_keyword and (has_company_keyword or has_market_keyword):
        # But pure finance knowledge questions should still use RAG.
        # Example: "现金流为什么重要？"
        if has_rag_keyword and not has_company_keyword:
            return QueryRoute.RAG_QA
        return QueryRoute.EVENT_ANALYSIS

    # Case 2:
    # Financial knowledge questions.
    if has_rag_keyword:
        return QueryRoute.RAG_QA

    # Case 3:
    # Market data questions.
    if has_market_keyword or has_company_keyword:
        return QueryRoute.MARKET_DATA

    return QueryRoute.GENERAL