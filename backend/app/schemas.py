from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        description="User question, such as 'BABA 最近 7 天涨跌情况如何？'",
    )


class ChatResponse(BaseModel):
    route: str
    answer: str
    sources: List[str] = []
    data: Optional[Dict[str, Any]] = None