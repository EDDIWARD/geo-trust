from __future__ import annotations

import json
import sys
from pathlib import Path

from app.rag_llm import chat_json, load_rag_llm_settings


SERVER_DIR = Path(__file__).resolve().parent
CORPUS_DIR = SERVER_DIR / "mock_data" / "rag_corpus"
OUTPUT_PATH = CORPUS_DIR / "knowledge_cards.json"


SYSTEM_PROMPT = """你是一个农业经营知识抽取助手。
你的任务不是写华丽报告，而是把资料整理成后续 RAG 可直接使用的结构化知识卡片。

必须遵守：
1. 只根据给定资料抽取，不得补充外部常识。
2. 不要把案例描述硬说成普遍规律。
3. 如果资料主要是案例或政策，就明确写“证据强度有限”。
4. 输出必须是 JSON 对象，不能带解释文字。
5. JSON 字符串内部不要使用英文双引号，不要输出 markdown，不要输出代码块。
6. 所有字段都必须存在；没有内容时返回空数组。
"""


def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    documents = json.loads((CORPUS_DIR / "documents.json").read_text(encoding="utf-8"))
    chunks = _load_jsonl(CORPUS_DIR / "chunks.jsonl")
    insights = _load_jsonl(CORPUS_DIR / "insights.jsonl")
    existing_cards = _load_existing_cards()
    existing_by_doc = {item["doc_id"]: item for item in existing_cards}

    cards: list[dict] = []
    settings = load_rag_llm_settings()
    processed = 0

    for document in documents:
        evidence = _build_evidence_bundle(document, chunks, insights)
        if document["doc_id"] in existing_by_doc:
            cards.append(_normalize_card(existing_by_doc[document["doc_id"]], document, evidence))
            continue

        payload = _build_prompt(document, evidence)
        card = chat_json(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=payload,
            temperature=0.0,
            settings=settings,
        )
        card = _normalize_card(card, document, evidence)
        card["doc_id"] = document["doc_id"]
        card["title"] = document["title"]
        card["source_path"] = document["source_path"]
        card["theme_path"] = document["theme_path"]
        cards.append(card)
        processed += 1

        if limit and processed >= limit:
            break

        _write_cards(cards + [existing_by_doc[key] for key in existing_by_doc if key not in {c["doc_id"] for c in cards}])

    final_cards = _merge_cards(existing_cards, cards)
    _write_cards(final_cards)
    print("knowledge-cards-built:", len(final_cards))


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _load_existing_cards() -> list[dict]:
    if not OUTPUT_PATH.exists():
        return []
    return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))


def _write_cards(cards: list[dict]) -> None:
    ordered = sorted(cards, key=lambda item: (item.get("theme_path", ""), item.get("title", "")))
    OUTPUT_PATH.write_text(json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8")


def _merge_cards(existing_cards: list[dict], new_cards: list[dict]) -> list[dict]:
    merged = {item["doc_id"]: item for item in existing_cards}
    for card in new_cards:
        merged[card["doc_id"]] = card
    return list(merged.values())


def _build_evidence_bundle(document: dict, chunks: list[dict], insights: list[dict]) -> dict:
    doc_chunks = [item for item in chunks if item["doc_id"] == document["doc_id"]]
    doc_insights = [item for item in insights if item["doc_id"] == document["doc_id"]]

    selected_chunks = sorted(
        doc_chunks,
        key=lambda item: (not item.get("is_conclusion_like", False), item["sequence"]),
    )[:6]
    selected_insights = sorted(
        doc_insights,
        key=lambda item: (item["insight_type"] != "strategy", -len(item["text"])),
    )[:10]

    return {
        "abstract": document["abstract"],
        "keywords": document["keywords"],
        "tags": document["tags"],
        "supported_questions": document["supported_questions"],
        "applicable_products": document["applicable_products"],
        "applicable_channels": document["applicable_channels"],
        "chunks": [
            {
                "chunk_id": item["chunk_id"],
                "text": item["text"][:900],
                "is_conclusion_like": item.get("is_conclusion_like", False),
            }
            for item in selected_chunks
        ],
        "insights": [
            {
                "insight_id": item["insight_id"],
                "insight_type": item["insight_type"],
                "text": item["text"],
            }
            for item in selected_insights
        ],
    }


def _build_prompt(document: dict, evidence: dict) -> str:
    schema = {
        "research_type": "paper | report | guideline | case | mixed",
        "evidence_strength": "high | medium | limited",
        "card_summary": "80到180字的中文摘要",
        "core_variables": ["变量1", "变量2"],
        "variable_relations": [
            {
                "statement": "变量关系描述",
                "direction": "positive | negative | mixed | unclear",
                "evidence_refs": ["insight_id或chunk_id"],
            }
        ],
        "key_findings": [
            {
                "finding": "关键结论",
                "evidence_refs": ["insight_id或chunk_id"],
            }
        ],
        "business_implications": [
            {
                "implication": "对商家经营判断有什么用",
                "evidence_refs": ["insight_id或chunk_id"],
            }
        ],
        "risk_warnings": ["哪些结论不能被过度泛化"],
        "recommended_queries": ["后续适合被检索命中的问题表达"],
    }

    return (
        f"请根据以下资料，为文档生成结构化知识卡片。\n\n"
        f"文档标题：{document['title']}\n"
        f"主题路径：{document['theme_path']}\n"
        f"来源文件：{document['source_path']}\n"
        f"文档标签：{json.dumps(document['tags'], ensure_ascii=False)}\n"
        f"支持问题：{json.dumps(document['supported_questions'], ensure_ascii=False)}\n"
        f"适用品类：{json.dumps(document['applicable_products'], ensure_ascii=False)}\n"
        f"适用渠道：{json.dumps(document['applicable_channels'], ensure_ascii=False)}\n\n"
        f"资料摘要：\n{evidence['abstract']}\n\n"
        f"关键词：{json.dumps(evidence['keywords'], ensure_ascii=False)}\n\n"
        f"候选 insight：\n{json.dumps(evidence['insights'], ensure_ascii=False, indent=2)}\n\n"
        f"候选 chunk：\n{json.dumps(evidence['chunks'], ensure_ascii=False, indent=2)}\n\n"
        f"请输出 JSON，对象结构必须严格遵循：\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        "补充要求：\n"
        "1. 只能返回一个 JSON 对象。\n"
        "2. 所有 value 一律使用普通字符串、数组、对象，不要加解释段落。\n"
        "3. 字符串里不要再嵌套英文双引号，必要时改用中文引号或直接改写。\n"
        "4. evidence_refs 只能引用给定的 insight_id 或 chunk_id。\n"
    )


def _normalize_card(card: dict, document: dict, evidence: dict) -> dict:
    valid_refs = {
        item["insight_id"]
        for item in evidence["insights"]
    } | {
        item["chunk_id"]
        for item in evidence["chunks"]
    }

    def normalize_refs(refs: list[str]) -> list[str]:
        normalized: list[str] = []
        for ref in refs:
            candidate = ref.strip()
            if candidate.startswith("chunk-"):
                candidate = f"{document['doc_id']}-{candidate}"
            if candidate in valid_refs and candidate not in normalized:
                normalized.append(candidate)
        return normalized

    for section_key in ("variable_relations", "key_findings", "business_implications"):
        section = card.get(section_key, [])
        if not isinstance(section, list):
            card[section_key] = []
            continue
        for item in section:
            refs = item.get("evidence_refs", [])
            if not isinstance(refs, list):
                item["evidence_refs"] = []
                continue
            item["evidence_refs"] = normalize_refs(refs)

    for key in (
        "core_variables",
        "risk_warnings",
        "recommended_queries",
    ):
        value = card.get(key, [])
        if not isinstance(value, list):
            card[key] = []

    return card


if __name__ == "__main__":
    main()
