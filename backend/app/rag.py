from pathlib import Path
from typing import Any, Dict, List

import chromadb


BACKEND_DIR = Path(__file__).resolve().parents[1]
DOCS_DIR = BACKEND_DIR / "docs"
CHROMA_DIR = BACKEND_DIR / "chroma_db"
COLLECTION_NAME = "finance_knowledge"

SOURCE_KEYWORDS = {
    "pe_ratio.md": [
        "市盈率",
        "pe",
        "p/e",
        "price earnings",
        "eps",
        "每股收益",
        "估值",
    ],
    "revenue_vs_net_income.md": [
        "收入",
        "营收",
        "revenue",
        "净利润",
        "net income",
        "profit",
        "top line",
        "bottom line",
        "区别",
    ],
    "cash_flow.md": [
        "现金流",
        "cash flow",
        "经营活动现金流",
        "投资活动现金流",
        "融资活动现金流",
        "operating cash flow",
    ],
    "balance_sheet.md": [
        "资产负债表",
        "balance sheet",
        "资产",
        "负债",
        "股东权益",
        "assets",
        "liabilities",
        "equity",
    ],
    "earnings_report_basics.md": [
        "季度财报",
        "财报摘要",
        "财报",
        "earnings",
        "quarterly report",
        "eps",
        "guidance",
        "业绩指引",
        "毛利率",
        "gross margin",
        "revenue",
        "net income",
    ],
}

def get_chroma_collection():
    """
    Create or load a persistent Chroma collection.

    Chroma stores document chunks and their vector embeddings locally.
    The database files will be saved under backend/chroma_db.
    """

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Small finance knowledge base for RAG QA"},
    )

    return collection


def read_markdown_files() -> List[Dict[str, str]]:
    """
    Read all markdown documents from backend/docs.
    """

    docs = []

    for path in sorted(DOCS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()

        if not text:
            continue

        docs.append(
            {
                "filename": path.name,
                "text": text,
            }
        )

    return docs


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> List[str]:
    """
    Split long text into overlapping chunks.

    Why overlap?
    Because important context may sit near the boundary of two chunks.
    Overlap helps preserve continuity.
    """

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start = end - overlap

        if start < 0:
            start = 0

        if start >= len(text):
            break

    return chunks


def build_rag_index() -> Dict[str, Any]:
    """
    Build or rebuild the RAG index from markdown docs.

    For MVP simplicity, we delete existing collection content and re-add all chunks.
    """

    collection = get_chroma_collection()

    # Delete previous records if they exist.
    existing = collection.get()

    if existing and existing.get("ids"):
        collection.delete(ids=existing["ids"])

    docs = read_markdown_files()

    ids = []
    documents = []
    metadatas = []

    for doc in docs:
        filename = doc["filename"]
        chunks = chunk_text(doc["text"])

        for i, chunk in enumerate(chunks):
            chunk_id = f"{filename}:chunk:{i}"

            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append(
                {
                    "source": filename,
                    "chunk_index": i,
                }
            )

    if documents:
        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

    return {
        "inserted_chunks": len(documents),
        "files": [doc["filename"] for doc in docs],
        "collection": COLLECTION_NAME,
        "persist_directory": str(CHROMA_DIR),
    }
def keyword_score(question: str, source: str, content: str) -> float:
    """
    Give a simple keyword-based relevance score.

    This is used as a reranking layer on top of vector search.
    It improves Chinese finance concept retrieval for the MVP.
    """

    q = question.lower()
    c = content.lower()

    score = 0.0

    # Source-specific keyword bonus
    for keyword in SOURCE_KEYWORDS.get(source, []):
        keyword_lower = keyword.lower()

        if keyword_lower in q:
            score += 5.0

        if keyword_lower in c:
            score += 1.0

    # Direct overlap between question terms and document content
    important_terms = [
        "市盈率",
        "收入",
        "净利润",
        "现金流",
        "资产负债表",
        "pe",
        "eps",
        "revenue",
        "net income",
        "cash flow",
        "balance sheet",
    ]

    for term in important_terms:
        if term.lower() in q and term.lower() in c:
            score += 3.0

    return score


def rerank_retrieved_docs(question: str, retrieved_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Rerank retrieved documents using keyword score + vector distance.

    Lower Chroma distance usually means more similar.
    Higher keyword score means more direct finance concept match.
    """

    reranked = []

    for doc in retrieved_docs:
        source = doc.get("source", "")
        content = doc.get("content", "")
        distance = doc.get("distance", 999.0)

        kw_score = keyword_score(question, source, content)

        # Combined score:
        # keyword_score is positive
        # distance is penalty
        final_score = kw_score - float(distance)

        new_doc = dict(doc)
        new_doc["keyword_score"] = round(kw_score, 4)
        new_doc["final_score"] = round(final_score, 4)

        reranked.append(new_doc)

    reranked.sort(key=lambda x: x["final_score"], reverse=True)

    return reranked


def retrieve_finance_docs(question: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Retrieve top-k relevant chunks from Chroma for a user question.

    We first retrieve more candidates from vector search, then rerank them
    using finance keyword matching. This improves accuracy for short Chinese queries.
    """

    collection = get_chroma_collection()

    candidate_k = max(top_k * 3, 6)

    result = collection.query(
        query_texts=[question],
        n_results=candidate_k,
    )

    docs = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    retrieved = []

    for doc, metadata, distance in zip(docs, metadatas, distances):
        retrieved.append(
            {
                "content": doc,
                "source": metadata.get("source"),
                "chunk_index": metadata.get("chunk_index"),
                "distance": distance,
            }
        )

    reranked = rerank_retrieved_docs(question, retrieved)

    return reranked[:top_k]

def build_rag_answer(question: str, retrieved_docs: List[Dict[str, Any]]) -> str:
    """
    Build a structured RAG answer without requiring an LLM.

    This version gives a cleaner professional answer while still showing sources.
    """

    if not retrieved_docs:
        return (
            "【未找到相关资料】\n"
            "本地金融知识库中没有检索到足够相关的内容，因此系统不会自由编造答案。\n\n"
            "【建议】\n"
            "你可以尝试换一种问法，或者扩充 docs/ 目录下的金融知识文档。"
        )

    top_doc = retrieved_docs[0]
    top_source = top_doc.get("source", "")
    top_content = top_doc.get("content", "")

    q = question.lower()

    if "市盈率" in question or "pe" in q or "p/e" in q:
        main_answer = (
            "市盈率，也叫 PE Ratio，是股票价格与每股收益 EPS 的比值。\n\n"
            "公式：PE = Stock Price / Earnings Per Share。\n\n"
            "它通常用来衡量市场愿意为公司每 1 元盈利支付多少价格。"
            "较高市盈率可能代表市场对未来增长有较高预期，也可能代表估值偏贵；"
            "较低市盈率可能代表估值较低，但也可能反映增长放缓或市场信心不足。"
        )

    elif "收入" in question and "净利润" in question:
        main_answer = (
            "收入 Revenue 是公司销售商品或提供服务获得的总金额，通常位于利润表最上方，也叫 top line。\n\n"
            "净利润 Net Income 是公司扣除成本、费用、利息和税费之后最终剩下的利润，通常位于利润表底部，也叫 bottom line。\n\n"
            "简单说，收入反映业务规模，净利润反映最终盈利能力。"
        )

    elif "现金流" in question or "cash flow" in q:
        main_answer = (
            "现金流 Cash Flow 指公司在一定时期内现金流入和流出的情况。\n\n"
            "现金流量表通常分为经营活动现金流、投资活动现金流和融资活动现金流。\n\n"
            "相比净利润，现金流更关注公司实际收到和支付的现金，因此常用于判断公司的真实财务健康状况。"
        )

    elif "资产负债表" in question or "balance sheet" in q:
        main_answer = (
            "资产负债表 Balance Sheet 展示公司在某一时间点的财务状况。\n\n"
            "核心公式是：Assets = Liabilities + Shareholders' Equity。\n\n"
            "它可以帮助分析公司的偿债能力、资本结构和财务稳定性。"
        )
    elif "财报" in question or "earnings" in q or "quarterly report" in q:
        main_answer = (
            "季度财报摘要通常用于快速理解公司在一个季度中的经营表现。\n\n"
            "核心指标包括营收 Revenue、净利润 Net Income、每股收益 EPS、毛利率 Gross Margin、"
            "经营现金流 Operating Cash Flow 和业绩指引 Guidance。\n\n"
            "如果要判断财报好坏，需要同时关注是否超出市场预期、增长是否加速、利润率是否改善、"
            "现金流是否健康，以及管理层是否上调或下调未来指引。\n\n"
            "当前知识库提供财报分析框架。如果要查询某公司真实最近季度财报，需要进一步接入 SEC、"
            "公司 Investor Relations 页面或财报 API。"
        )

    else:
        main_answer = (
            "系统已从本地金融知识库中检索到相关资料。"
            "当前问题没有命中特定模板，因此下面给出最相关资料的摘要。\n\n"
            f"{top_content}"
        )

    sources = sorted({doc["source"] for doc in retrieved_docs if doc.get("source")})

    retrieved_summary = "\n".join(
        [
            f"- {doc['source']} | chunk {doc['chunk_index']} | "
            f"keyword_score={doc.get('keyword_score')} | final_score={doc.get('final_score')}"
            for doc in retrieved_docs
        ]
    )

    return (
        f"【问题】\n"
        f"{question}\n\n"
        f"【回答】\n"
        f"{main_answer}\n\n"
        f"【知识库依据】\n"
        f"本回答基于本地 RAG 知识库检索结果生成，最相关来源为：{top_source}。\n\n"
        f"【检索到的资料】\n"
        f"{retrieved_summary}\n\n"
        f"【来源】\n"
        + "\n".join(f"- {source}" for source in sources)
        + "\n\n【说明】\n"
        "该回答没有直接依赖模型自由发挥，而是基于本地知识库检索结果生成。"
    )