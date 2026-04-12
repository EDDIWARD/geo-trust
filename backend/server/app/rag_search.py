from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path


CORPUS_DIR = Path(__file__).resolve().parents[1] / "mock_data" / "rag_corpus"


def search_rag(query: str, top_k: int = 5) -> dict:
    documents = _load_documents()
    cards = _load_cards()
    chunks = _load_jsonl(CORPUS_DIR / "chunks.jsonl")
    insights = _load_jsonl(CORPUS_DIR / "insights.jsonl")

    ranked_docs = _rank_documents(query, documents, top_k=top_k)
    ranked_cards = _rank_cards(query, cards, top_k=top_k)
    selected_doc_ids = {item["doc_id"] for item in ranked_docs} | {item["doc_id"] for item in ranked_cards}
    ranked_chunks = _rank_chunks(query, [item for item in chunks if item["doc_id"] in selected_doc_ids], top_k=top_k * 2)
    ranked_insights = _rank_insights(query, [item for item in insights if item["doc_id"] in selected_doc_ids], top_k=top_k * 3)

    return {
        "query": query,
        "documents": ranked_docs,
        "cards": ranked_cards,
        "chunks": ranked_chunks,
        "insights": ranked_insights,
    }


@lru_cache(maxsize=1)
def _load_documents() -> list[dict]:
    return json.loads((CORPUS_DIR / "documents.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_cards() -> list[dict]:
    path = CORPUS_DIR / "knowledge_cards.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _rank_documents(query: str, documents: list[dict], top_k: int) -> list[dict]:
    tokens = _query_tokens(query)
    scored: list[dict] = []
    for document in documents:
        title = document["title"]
        abstract = document["abstract"]
        tags = " ".join(document["tags"])
        questions = " ".join(document["supported_questions"])
        score = (
            4.0 * _keyword_score(tokens, title)
            + 2.5 * _keyword_score(tokens, tags)
            + 2.0 * _keyword_score(tokens, questions)
            + 1.2 * _keyword_score(tokens, abstract[:1200])
        )
        if score <= 0:
            continue
        scored.append(
            {
                "doc_id": document["doc_id"],
                "title": title,
                "source_path": document["source_path"],
                "theme_path": document["theme_path"],
                "tags": document["tags"],
                "supported_questions": document["supported_questions"],
                "score": round(score, 4),
            }
        )
    return sorted(scored, key=lambda item: item["score"], reverse=True)[:top_k]


def _rank_chunks(query: str, chunks: list[dict], top_k: int) -> list[dict]:
    tokens = _query_tokens(query)
    scored: list[dict] = []
    for chunk in chunks:
        text = chunk["text"]
        score = (
            3.2 * _keyword_score(tokens, text[:400])
            + 1.4 * _keyword_score(tokens, " ".join(chunk["tags"]))
            + (1.0 if chunk.get("is_conclusion_like") else 0.0)
        )
        if score <= 0:
            continue
        scored.append(
            {
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "title": chunk["title"],
                "theme_path": chunk["theme_path"],
                "score": round(score, 4),
                "text": text[:360],
            }
        )
    return sorted(scored, key=lambda item: item["score"], reverse=True)[:top_k]


def _rank_cards(query: str, cards: list[dict], top_k: int) -> list[dict]:
    tokens = _query_tokens(query)
    scored: list[dict] = []
    for card in cards:
        summary = card.get("card_summary", "")
        title = card.get("title", "")
        variables = " ".join(card.get("core_variables", []))
        findings = " ".join(item.get("finding", "") for item in card.get("key_findings", []))
        implications = " ".join(item.get("implication", "") for item in card.get("business_implications", []))
        queries = " ".join(card.get("recommended_queries", []))
        tags = " ".join(card.get("core_variables", []) + [card.get("research_type", ""), card.get("evidence_strength", "")])
        score = (
            4.0 * _keyword_score(tokens, title)
            + 3.0 * _keyword_score(tokens, summary)
            + 2.4 * _keyword_score(tokens, findings)
            + 2.0 * _keyword_score(tokens, implications)
            + 1.8 * _keyword_score(tokens, queries)
            + 1.5 * _keyword_score(tokens, variables)
            + 1.0 * _keyword_score(tokens, tags)
        )
        if score <= 0:
            continue
        scored.append(
            {
                "doc_id": card["doc_id"],
                "title": title,
                "theme_path": card["theme_path"],
                "score": round(score, 4),
                "research_type": card.get("research_type", ""),
                "evidence_strength": card.get("evidence_strength", ""),
                "card_summary": summary,
                "core_variables": card.get("core_variables", []),
                "business_implications": [item.get("implication", "") for item in card.get("business_implications", [])],
                "recommended_queries": card.get("recommended_queries", []),
            }
        )
    return sorted(scored, key=lambda item: item["score"], reverse=True)[:top_k]


def _rank_insights(query: str, insights: list[dict], top_k: int) -> list[dict]:
    tokens = _query_tokens(query)
    scored: list[dict] = []
    for insight in insights:
        text = insight["text"]
        base = 4.0 * _keyword_score(tokens, text)
        if insight["insight_type"] == "strategy":
            base += 0.8
        elif insight["insight_type"] == "conclusion":
            base += 0.5
        if base <= 0:
            continue
        scored.append(
            {
                "insight_id": insight["insight_id"],
                "doc_id": insight["doc_id"],
                "title": insight["title"],
                "insight_type": insight["insight_type"],
                "theme_path": insight["theme_path"],
                "score": round(base, 4),
                "text": text,
            }
        )
    return sorted(scored, key=lambda item: item["score"], reverse=True)[:top_k]


def _query_tokens(query: str) -> list[str]:
    query = re.sub(r"\s+", "", query.strip())
    if not query:
        return []
    tokens: list[str] = []
    for size in (2, 3, 4):
        if len(query) < size:
            continue
        for index in range(len(query) - size + 1):
            token = query[index:index + size]
            if token not in tokens:
                tokens.append(token)
    if query not in tokens:
        tokens.insert(0, query)
    return tokens[:48]


def _keyword_score(tokens: list[str], text: str) -> float:
    normalized = text.replace(" ", "")
    score = 0.0
    for token in tokens:
        if token and token in normalized:
            score += min(len(token) / 2, 2.0)
    return score
