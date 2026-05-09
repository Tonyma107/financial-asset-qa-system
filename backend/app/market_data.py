import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
CACHE_DIR = BACKEND_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

load_dotenv(BACKEND_DIR / ".env")


def detect_period_days(question: str) -> int:
    """
    Detect requested time window from the user's question.
    """

    q = question.lower()

    if "7天" in q or "7 天" in q or "7d" in q or "7 days" in q:
        return 7

    if "30天" in q or "30 天" in q or "30d" in q or "30 days" in q:
        return 30

    # Event analysis usually needs more historical data.
    if "月" in q or "2026-" in q or "2025-" in q:
        return 252

    return 30


def classify_trend(change_pct: float) -> str:
    """
    Classify historical trend.
    This is descriptive only, not a prediction.
    """

    if change_pct >= 3:
        return "上涨"
    if change_pct <= -3:
        return "下跌"
    return "震荡"


def _cache_path(ticker: str, period_days: int) -> Path:
    return CACHE_DIR / f"{ticker.upper()}_{period_days}d.json"


def _load_cached_history(ticker: str, period_days: int, max_age_hours: int = 24) -> pd.DataFrame:
    """
    Load cached market data if available and not too old.
    """

    path = _cache_path(ticker, period_days)

    if not path.exists():
        return pd.DataFrame()

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))

        cached_at = datetime.fromisoformat(payload["cached_at"])
        if datetime.utcnow() - cached_at > timedelta(hours=max_age_hours):
            return pd.DataFrame()

        records = payload.get("records", [])
        if not records:
            return pd.DataFrame()

        return pd.DataFrame(records)

    except Exception:
        return pd.DataFrame()


def _save_cached_history(ticker: str, period_days: int, df: pd.DataFrame) -> None:
    """
    Save successful market data to local cache.
    """

    path = _cache_path(ticker, period_days)

    payload = {
        "ticker": ticker.upper(),
        "period_days": period_days,
        "cached_at": datetime.utcnow().isoformat(),
        "records": df.to_dict(orient="records"),
    }

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _clean_history_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize market data dataframe.
    """

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    if "Date" not in df.columns:
        df = df.reset_index()

    rename_map = {}

    for col in df.columns:
        lower = str(col).lower()

        if lower == "date":
            rename_map[col] = "Date"
        elif lower == "open":
            rename_map[col] = "Open"
        elif lower == "high":
            rename_map[col] = "High"
        elif lower == "low":
            rename_map[col] = "Low"
        elif lower == "close":
            rename_map[col] = "Close"
        elif lower == "volume":
            rename_map[col] = "Volume"

    df = df.rename(columns=rename_map)

    if "Close" not in df.columns:
        return pd.DataFrame()

    df = df.dropna(subset=["Close"])

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")

    keep_cols = [col for col in ["Date", "Open", "High", "Low", "Close", "Volume"] if col in df.columns]
    df = df[keep_cols]

    return df


def _fetch_alpha_vantage_history(ticker: str, period_days: int) -> Tuple[pd.DataFrame, str]:
    """
    Fetch daily stock price data from Alpha Vantage.

    Requires:
    ALPHA_VANTAGE_API_KEY in backend/.env
    """

    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")

    if not api_key:
        raise ValueError("Missing ALPHA_VANTAGE_API_KEY in backend/.env")

    url = "https://www.alphavantage.co/query"

    # Free Alpha Vantage API supports compact output for recent daily data.
    # We avoid outputsize=full because it may require a premium plan.
    outputsize = "compact"

    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": ticker.upper(),
        "outputsize": outputsize,
        "apikey": api_key,
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    payload = response.json()

    if "Error Message" in payload:
        raise ValueError(f"Alpha Vantage error: {payload['Error Message']}")

    if "Note" in payload:
        raise ValueError(f"Alpha Vantage rate limit note: {payload['Note']}")

    if "Information" in payload:
        raise ValueError(f"Alpha Vantage information: {payload['Information']}")

    time_series = payload.get("Time Series (Daily)")

    if not time_series:
        preview = str(payload)[:300]
        raise ValueError(f"Alpha Vantage returned no daily time series. Preview: {preview}")

    rows = []

    for date_str, values in time_series.items():
        rows.append(
            {
                "Date": date_str,
                "Open": float(values["1. open"]),
                "High": float(values["2. high"]),
                "Low": float(values["3. low"]),
                "Close": float(values["4. close"]),
                "Volume": float(values["5. volume"]),
            }
        )

    df = pd.DataFrame(rows)
    df = _clean_history_df(df)

    if df.empty:
        raise ValueError(f"Alpha Vantage returned empty dataframe for ticker {ticker}")

    df = df.sort_values("Date").reset_index(drop=True)

    return df, "Alpha Vantage TIME_SERIES_DAILY"


def _fetch_yfinance_history(ticker: str, period_days: int) -> Tuple[pd.DataFrame, str]:
    """
    Fetch market data from yfinance as fallback.
    """

    if period_days <= 30:
        yf_period = "3mo"
    elif period_days <= 252:
        yf_period = "1y"
    else:
        yf_period = "2y"

    stock = yf.Ticker(ticker.upper())
    hist = stock.history(period=yf_period, interval="1d")

    df = _clean_history_df(hist)

    if df.empty:
        raise ValueError(f"No yfinance data returned for ticker {ticker}")

    df = df.sort_values("Date").reset_index(drop=True)

    return df, "Yahoo Finance via yfinance"


def _fetch_history_with_fallback(ticker: str, period_days: int) -> Tuple[pd.DataFrame, str, List[str]]:
    """
    Fetch market data with provider fallback.

    Priority:
    1. Alpha Vantage
    2. yfinance
    3. local cache

    This avoids hallucinating market data when APIs fail.
    """

    warnings: List[str] = []

    try:
        df, source = _fetch_alpha_vantage_history(ticker, period_days)
        _save_cached_history(ticker, period_days, df)
        return df, source, warnings
    except Exception as e:
        warnings.append(f"Alpha Vantage failed: {str(e)}")

    try:
        df, source = _fetch_yfinance_history(ticker, period_days)
        _save_cached_history(ticker, period_days, df)
        return df, source, warnings
    except Exception as e:
        warnings.append(f"yfinance failed: {str(e)}")

    cached_df = _load_cached_history(ticker, period_days)

    if not cached_df.empty:
        warnings.append("Using local cached market data because external providers failed.")
        return cached_df, "Local cache from previous market data result", warnings

    raise RuntimeError("; ".join(warnings))


def _records_for_frontend(df: pd.DataFrame, max_rows: int = 30) -> List[Dict[str, Any]]:
    """
    Return compact price history records for frontend chart/table.
    """

    keep_cols = [col for col in ["Date", "Open", "High", "Low", "Close", "Volume"] if col in df.columns]
    compact = df[keep_cols].tail(max_rows).copy()

    records = []

    for _, row in compact.iterrows():
        item = {}

        for col in keep_cols:
            value = row[col]

            if pd.isna(value):
                item[col] = None
            elif col == "Date":
                item[col] = str(value)
            else:
                item[col] = round(float(value), 4)

        records.append(item)

    return records


def get_market_summary(ticker: str, question: str) -> Dict[str, Any]:
    """
    Main market data function.

    It fetches market history, computes return, classifies trend,
    and returns structured data for answer generation.
    """

    period_days = detect_period_days(question)

    df, source, warnings = _fetch_history_with_fallback(ticker, period_days)

    if "Date" in df.columns:
        df = df.sort_values("Date").reset_index(drop=True)

    period_df = df.tail(period_days)

    if len(period_df) < 2:
        raise ValueError(f"Not enough historical data for ticker {ticker}")

    start_row = period_df.iloc[0]
    end_row = period_df.iloc[-1]

    start_price = float(start_row["Close"])
    latest_price = float(end_row["Close"])

    change = latest_price - start_price
    change_pct = (change / start_price) * 100

    high_price = float(period_df["High"].max()) if "High" in period_df.columns else None
    low_price = float(period_df["Low"].min()) if "Low" in period_df.columns else None

    return {
        "ticker": ticker.upper(),
        "period_days": period_days,
        "data_source": source,
        "provider_warnings": warnings,
        "start_date": str(start_row["Date"]) if "Date" in period_df.columns else None,
        "end_date": str(end_row["Date"]) if "Date" in period_df.columns else None,
        "start_close": round(start_price, 2),
        "latest_close": round(latest_price, 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "high": round(high_price, 2) if high_price is not None else None,
        "low": round(low_price, 2) if low_price is not None else None,
        "trend": classify_trend(change_pct),
        "history": _records_for_frontend(period_df),
        "last_updated": datetime.utcnow().isoformat() + "Z",
    }


def build_market_answer(question: str, market: Dict[str, Any]) -> str:
    """
    Build a structured market answer without relying on LLM.
    """

    warnings = market.get("provider_warnings") or []
    warning_text = ""

    if warnings:
        warning_text = "\n\n【数据源提示】\n" + "\n".join(f"- {w}" for w in warnings)

    return (
        f"【结论】\n"
        f"{market['ticker']} 在最近 {market['period_days']} 个交易日内整体呈现：{market['trend']}。\n\n"
        f"【客观数据】\n"
        f"- 股票代码：{market['ticker']}\n"
        f"- 起始日期：{market['start_date']}\n"
        f"- 结束日期：{market['end_date']}\n"
        f"- 起始收盘价：{market['start_close']}\n"
        f"- 最新收盘价：{market['latest_close']}\n"
        f"- 区间涨跌额：{market['change']}\n"
        f"- 区间涨跌幅：{market['change_pct']}%\n"
        f"- 区间最高价：{market['high']}\n"
        f"- 区间最低价：{market['low']}\n\n"
        f"【趋势分析】\n"
        f"本系统根据历史收盘价变化进行趋势判断。该判断只描述历史走势，不代表未来预测。\n\n"
        f"【数据来源】\n"
        f"- {market['data_source']}\n"
        f"- Last updated: {market['last_updated']}"
        f"{warning_text}\n\n"
        f"【风险提示】\n"
        f"以上内容基于公开历史行情数据自动计算，不构成投资建议。"
    )