

import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pandas as pd

from app.market_data import _fetch_history_with_fallback

def parse_event_date(question: str) -> Optional[str]:
    """
    Parse event date from Chinese, English, or relative date expressions.

    Supported examples:
    - 今天
    - 昨天
    - 上周五
    - 上周
    - 1 月 15 日
    - 2026 年 1 月 15 日
    - 2026-01-15
    - 2026/01/15

    Return format: YYYY-MM-DD
    """

    today = datetime.now().date()
    current_year = today.year

    q = question.strip()

    # Relative date: today / yesterday
    if "今天" in q:
        return today.strftime("%Y-%m-%d")

    if "昨天" in q:
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")

    # Chinese weekday mapping
    weekday_map = {
        "一": 0,
        "二": 1,
        "三": 2,
        "四": 3,
        "五": 4,
        "六": 5,
        "日": 6,
        "天": 6,
    }

    # 上周五 / 上周三 / 上周日
    last_weekday_match = re.search(r"上周([一二三四五六日天])", q)
    if last_weekday_match:
        target_weekday = weekday_map[last_weekday_match.group(1)]

        # Monday of current week
        current_monday = today - timedelta(days=today.weekday())

        # Monday of last week
        last_monday = current_monday - timedelta(days=7)

        target_date = last_monday + timedelta(days=target_weekday)
        return target_date.strftime("%Y-%m-%d")

    # 上周 without weekday:
    # For a single-date event analysis MVP, use last Friday as representative.
    if "上周" in q:
        current_monday = today - timedelta(days=today.weekday())
        last_friday = current_monday - timedelta(days=3)
        return last_friday.strftime("%Y-%m-%d")

    # Match YYYY-MM-DD or YYYY/MM/DD
    full_date_match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", q)
    if full_date_match:
        year = int(full_date_match.group(1))
        month = int(full_date_match.group(2))
        day = int(full_date_match.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"

    # Match Chinese full date:
    # 2020 年 3 月 1 日
    # 2020年3月1日
    chinese_full_date_match = re.search(
        r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        q,
    )
    if chinese_full_date_match:
        year = int(chinese_full_date_match.group(1))
        month = int(chinese_full_date_match.group(2))
        day = int(chinese_full_date_match.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"

    # Match Chinese date without year:
    # 1 月 15 日
    # 1月15日
    chinese_date_match = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日", q)
    if chinese_date_match:
        month = int(chinese_date_match.group(1))
        day = int(chinese_date_match.group(2))
        return f"{current_year:04d}-{month:02d}-{day:02d}"

    return None

def check_date_in_data_range(df: pd.DataFrame, target_date: str) -> Optional[Dict[str, Any]]:
    """
    Check whether target date is covered by the available market data.

    This prevents a serious hallucination risk:
    If user asks for 2020 but compact API only contains 2026 data,
    the system must not silently use a nearby 2026 trading day.
    """

    if df.empty or "Date" not in df.columns:
        return {
            "status": "insufficient_data",
            "message": "行情数据为空，无法判断日期范围。",
        }

    date_series = pd.to_datetime(df["Date"])
    target = pd.to_datetime(target_date)

    min_date = date_series.min()
    max_date = date_series.max()

    if target < min_date:
        return {
            "status": "out_of_range",
            "message": (
                f"用户询问日期 {target_date} 早于当前可用行情数据范围。"
                f"当前数据范围为 {min_date.strftime('%Y-%m-%d')} 到 {max_date.strftime('%Y-%m-%d')}。"
            ),
            "available_start_date": min_date.strftime("%Y-%m-%d"),
            "available_end_date": max_date.strftime("%Y-%m-%d"),
        }

    if target > max_date:
        return {
            "status": "out_of_range",
            "message": (
                f"用户询问日期 {target_date} 晚于当前可用行情数据范围。"
                f"当前数据范围为 {min_date.strftime('%Y-%m-%d')} 到 {max_date.strftime('%Y-%m-%d')}。"
            ),
            "available_start_date": min_date.strftime("%Y-%m-%d"),
            "available_end_date": max_date.strftime("%Y-%m-%d"),
        }

    return None

def _find_nearest_trading_row(df: pd.DataFrame, target_date: str) -> Optional[int]:
    """
    Find the nearest trading day on or before the target date.

    Why?
    The target date may be weekend or market holiday.
    """

    if df.empty or "Date" not in df.columns:
        return None

    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    target = pd.to_datetime(target_date)

    eligible = df[df["Date"] <= target]

    if eligible.empty:
        return None

    return int(eligible.index[-1])


def analyze_event_movement(ticker: str, question: str) -> Dict[str, Any]:
    """
    Analyze stock movement around a user-specified event date.

    This function focuses on objective market data:
    - event date
    - nearest trading date
    - previous close
    - event day close
    - event day return
    - volume compared with recent average
    """

    event_date = parse_event_date(question)

    if event_date is None:
        return {
            "ticker": ticker,
            "event_date": None,
            "status": "missing_date",
            "message": "系统没有从问题中识别出明确日期。",
        }

    # Use around one year of data so Jan dates are likely included.
    df, source, warnings = _fetch_history_with_fallback(ticker, period_days=252)

    if "Date" in df.columns:
        df = df.sort_values("Date").reset_index(drop=True)
    range_error = check_date_in_data_range(df, event_date)
    if range_error is not None:
        return {
            "ticker": ticker,
            "event_date": event_date,
            "status": range_error["status"],
            "message": range_error["message"],
            "available_start_date": range_error.get("available_start_date"),
            "available_end_date": range_error.get("available_end_date"),
            "data_source": source,
            "provider_warnings": warnings,
        }
    row_idx = _find_nearest_trading_row(df, event_date)

    if row_idx is None or row_idx == 0:
        return {
            "ticker": ticker,
            "event_date": event_date,
            "status": "insufficient_data",
            "message": (
                "系统没有足够历史行情数据来分析该日期。"
                "如果使用 Alpha Vantage 免费版，compact 数据通常只覆盖最近一段交易日。"
            ),
            "data_source": source,
            "provider_warnings": warnings,
        }

    event_row = df.iloc[row_idx]
    prev_row = df.iloc[row_idx - 1]

    event_close = float(event_row["Close"])
    prev_close = float(prev_row["Close"])

    daily_change = event_close - prev_close
    daily_change_pct = (daily_change / prev_close) * 100

    # Recent volume average before event day.
    volume_analysis = None

    if "Volume" in df.columns:
        lookback_start = max(0, row_idx - 10)
        recent_volume = df.iloc[lookback_start:row_idx]["Volume"].dropna()

        if len(recent_volume) > 0:
            avg_volume = float(recent_volume.mean())
            event_volume = float(event_row["Volume"])
            volume_ratio = event_volume / avg_volume if avg_volume > 0 else None

            volume_analysis = {
                "event_volume": round(event_volume, 2),
                "avg_volume_prior_10_trading_days": round(avg_volume, 2),
                "volume_ratio": round(volume_ratio, 2) if volume_ratio is not None else None,
            }

    if daily_change_pct >= 3:
        movement_label = "明显上涨"
    elif daily_change_pct <= -3:
        movement_label = "明显下跌"
    else:
        movement_label = "小幅波动/震荡"

    return {
        "ticker": ticker,
        "event_date": event_date,
        "nearest_trading_date": str(event_row["Date"]),
        "previous_trading_date": str(prev_row["Date"]),
        "previous_close": round(prev_close, 2),
        "event_close": round(event_close, 2),
        "daily_change": round(daily_change, 2),
        "daily_change_pct": round(daily_change_pct, 2),
        "movement_label": movement_label,
        "volume_analysis": volume_analysis,
        "data_source": source,
        "provider_warnings": warnings,
        "status": "ok",
    }


def build_event_answer(question: str, event: Dict[str, Any]) -> str:
    """
    Build a transparent event-analysis answer.

    This version does not hallucinate news.
    It only uses verified price/volume data and gives possible analysis directions.
    """

    if event.get("status") == "missing_date":
        return (
            "【事件分析失败】\n"
            "系统没有从问题中识别出明确日期。\n\n"
            "【建议问法】\n"
            "- 阿里巴巴为何 2026-01-15 大涨？\n"
            "- BABA 为何 1 月 15 日大涨？"
        )
    if event.get("status") == "out_of_range":
        return (
            "【事件分析失败】\n"
            "系统无法查询该日期的行情数据，因此不会生成可能误导的结论。\n\n"
            f"【原因】\n"
            f"{event.get('message')}\n\n"
            f"【可用数据范围】\n"
            f"- 开始日期：{event.get('available_start_date')}\n"
            f"- 结束日期：{event.get('available_end_date')}\n\n"
            "【建议】\n"
            "- 请查询可用数据范围内的日期；\n"
            "- 如果需要更早年份的数据，请切换到支持更长历史数据的行情 API；\n"
            "- 系统不会把 2020 年的问题错误映射到 2026 年数据。"
        )
    
    if event.get("status") == "insufficient_data":
        return (
            "【事件分析失败】\n"
            "系统没有足够历史行情数据来分析该日期。\n\n"
            f"【数据源】\n{event.get('data_source')}\n\n"
            "【建议】\n"
            "你可以尝试更近的日期，或者切换更完整的行情数据源。"
        )
    

    volume_text = "暂无成交量对比数据。"
    volume = event.get("volume_analysis")

    if volume:
        volume_text = (
            f"- 当日成交量：{volume['event_volume']}\n"
            f"- 前 10 个交易日平均成交量：{volume['avg_volume_prior_10_trading_days']}\n"
            f"- 成交量倍数：{volume['volume_ratio']}x"
        )

    warnings = event.get("provider_warnings") or []
    warning_text = ""

    if warnings:
        warning_text = "\n\n【数据源提示】\n" + "\n".join(f"- {w}" for w in warnings)

    return (
        f"【结论】\n"
        f"{event['ticker']} 在 {event['nearest_trading_date']} 的行情表现为：{event['movement_label']}。\n"
        f"当日涨跌幅为 {event['daily_change_pct']}%。\n\n"
        f"【客观行情数据】\n"
        f"- 股票代码：{event['ticker']}\n"
        f"- 用户询问日期：{event['event_date']}\n"
        f"- 实际匹配交易日：{event['nearest_trading_date']}\n"
        f"- 前一交易日：{event['previous_trading_date']}\n"
        f"- 前一交易日收盘价：{event['previous_close']}\n"
        f"- 当日收盘价：{event['event_close']}\n"
        f"- 当日涨跌额：{event['daily_change']}\n"
        f"- 当日涨跌幅：{event['daily_change_pct']}%\n\n"
        f"【成交量观察】\n"
        f"{volume_text}\n\n"
        f"【可能影响因素分析】\n"
        f"当前版本已经验证了该日期附近的客观行情变化，但没有接入可靠新闻搜索 API，"
        f"因此系统不会编造具体新闻原因。\n\n"
        f"通常解释单日大涨/大跌时，可以进一步检查：\n"
        f"1. 公司财报或业绩指引是否超预期；\n"
        f"2. 管理层讲话、回购、分红、监管政策等公司事件；\n"
        f"3. 行业板块整体上涨或下跌；\n"
        f"4. 宏观利率、汇率、通胀数据或市场风险偏好变化；\n"
        f"5. 是否存在高成交量确认，说明市场参与度明显上升。\n\n"
        f"【数据来源】\n"
        f"- {event['data_source']}"
        f"{warning_text}\n\n"
        f"【不确定性说明】\n"
        f"以上分析只基于历史行情和成交量。若要判断真正原因，需要进一步接入新闻搜索、公告、财报或 SEC 文件。"
        f"本回答不构成投资建议。"
    )