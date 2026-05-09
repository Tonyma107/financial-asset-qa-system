import re
from typing import Optional


# A small alias table for the MVP.
# In a production system, this could be replaced by a real symbol search API.
TICKER_ALIASES = {
    # Alibaba
    "阿里巴巴": "BABA",
    "阿里": "BABA",
    "alibaba": "BABA",
    "baba": "BABA",

    # Tesla
    "特斯拉": "TSLA",
    "tesla": "TSLA",
    "tsla": "TSLA",

    # Apple
    "苹果": "AAPL",
    "apple": "AAPL",
    "aapl": "AAPL",

    # Nvidia
    "英伟达": "NVDA",
    "nvidia": "NVDA",
    "nvda": "NVDA",

    # Microsoft
    "微软": "MSFT",
    "microsoft": "MSFT",
    "msft": "MSFT",

    # Amazon
    "亚马逊": "AMZN",
    "amazon": "AMZN",
    "amzn": "AMZN",

    # Google / Alphabet
    "谷歌": "GOOGL",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "googl": "GOOGL",

    # Meta
    "meta": "META",
    "facebook": "META",
    "脸书": "META",

        # Tencent
    "腾讯": "TCEHY",
    "腾讯控股": "TCEHY",
    "tencent": "TCEHY",
    "tcehy": "TCEHY",

    # TSMC
    "台积电": "TSM",
    "台湾积体电路": "TSM",
    "tsmc": "TSM",
    "tsm": "TSM",

    # JD
    "京东": "JD",
    "jd": "JD",
    "jd.com": "JD",

    # PDD
    "拼多多": "PDD",
    "pdd": "PDD",
    "pinduoduo": "PDD",

    # Baidu
    "百度": "BIDU",
    "baidu": "BIDU",
    "bidu": "BIDU",

    # BYD
    "比亚迪": "BYDDY",
    "byd": "BYDDY",
    "byddy": "BYDDY",

    # Xiaomi
    "小米": "XIACF",
    "xiaomi": "XIACF",
    "xiacf": "XIACF",
}


# These uppercase words are common finance / system terms, not stock tickers.
NON_TICKER_WORDS = {
    "PE",
    "EPS",
    "API",
    "RAG",
    "LLM",
    "AI",
    "GDP",
    "CPI",
    "ETF",
    "USD",
}


def resolve_ticker(question: str) -> Optional[str]:
    """
    Resolve a company name or explicit ticker symbol from the user question.

    Examples:
    - 阿里巴巴当前股价是多少？ -> BABA
    - BABA 最近 7 天涨跌情况如何？ -> BABA
    - 特斯拉近期走势如何？ -> TSLA
    """

    q_lower = question.lower()

    # First, match known aliases such as 阿里巴巴, 特斯拉, tesla, baba.
    for alias, ticker in TICKER_ALIASES.items():
        if alias.lower() in q_lower:
            return ticker

    # Second, detect explicit ticker-like uppercase symbols.
    # Example: "BABA 最近 7 天涨跌情况如何？"
    candidates = re.findall(r"\b[A-Z]{1,5}\b", question)

    for candidate in candidates:
        if candidate not in NON_TICKER_WORDS:
            return candidate

    return None