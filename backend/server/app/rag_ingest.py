from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader


TEXT_EXTENSIONS = {".html", ".htm", ".pdf", ".md", ".txt"}
SKIP_DIR_NAMES = {"00_资料清单", "99_待核验", "__pycache__"}
SKIP_FILE_NAMES = {"README.md", "学术资料清单.md", "RAG资料入库清单.md"}
CONCLUSION_PATTERNS = (
    "研究表明",
    "研究发现",
    "结果表明",
    "结果显示",
    "实证表明",
    "实证结果",
    "显著正向",
    "显著负向",
    "有显著影响",
    "建议",
    "启示",
)
PRODUCT_KEYWORDS = {
    "茶": "茶叶",
    "咖啡": "咖啡",
    "坚果": "坚果",
    "水果": "水果",
    "生鲜": "生鲜",
    "农产品": "综合农产品",
    "有机": "有机农产品",
    "地理标志": "地理标志农产品",
}
CHANNEL_KEYWORDS = {
    "电商": "电商",
    "网购": "电商",
    "直播": "直播",
    "社区团购": "社区团购",
    "礼盒": "礼赠",
    "商超": "商超",
    "渠道": "渠道策略",
}
QUESTION_KEYWORDS = {
    "购买意愿": "消费者是否愿意买",
    "支付意愿": "消费者是否愿意为特定属性多付钱",
    "品牌": "品牌建设或品牌表达应怎么做",
    "地理标志": "产地标签和地理标志能否支撑溢价",
    "信任": "信任机制如何影响转化",
    "溯源": "溯源与透明信息对购买有没有帮助",
    "包装": "包装和礼盒会加分还是减分",
    "礼盒": "礼盒化适不适合该商品",
    "社区团购": "社区团购是否适合该商品",
    "电商": "线上渠道应怎么选",
    "网购": "线上购买决策受什么影响",
}


@dataclass
class RagDocument:
    doc_id: str
    title: str
    source_path: str
    file_type: str
    theme_path: str
    source_group: str
    tags: list[str]
    applicable_products: list[str]
    applicable_channels: list[str]
    supported_questions: list[str]
    abstract: str
    keywords: list[str]
    full_text: str
    text_length: int


@dataclass
class RagChunk:
    chunk_id: str
    doc_id: str
    title: str
    sequence: int
    text: str
    text_length: int
    theme_path: str
    tags: list[str]
    is_conclusion_like: bool


@dataclass
class RagInsight:
    insight_id: str
    doc_id: str
    title: str
    source_chunk_id: str
    text: str
    insight_type: str
    theme_path: str
    tags: list[str]


class _HtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._parts: list[str] = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        lower_tag = tag.lower()
        if lower_tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        if lower_tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        lower_tag = tag.lower()
        if lower_tag in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1
        if lower_tag == "title":
            self._in_title = False
        if lower_tag in {"p", "div", "section", "article", "li", "tr", "br", "h1", "h2", "h3", "h4"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        text = data.strip()
        if not text:
            return
        if self._in_title and not self.title:
            self.title = text
        self._parts.append(text)

    def text(self) -> str:
        return "".join(self._parts)


def iter_source_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        if path.name in SKIP_FILE_NAMES:
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        yield path


def build_rag_corpus(source_root: Path) -> tuple[list[RagDocument], list[RagChunk], list[RagInsight]]:
    documents: list[RagDocument] = []
    chunks: list[RagChunk] = []
    insights: list[RagInsight] = []

    for path in iter_source_files(source_root):
        document = extract_document(path, source_root)
        if document is None:
            continue
        documents.append(document)
        doc_chunks = split_document_into_chunks(document)
        chunks.extend(doc_chunks)
        insights.extend(extract_insights(document, doc_chunks))

    return documents, chunks, insights


def extract_document(path: Path, source_root: Path) -> RagDocument | None:
    raw_text, extracted_title = _extract_raw_text(path)
    cleaned_text = clean_text(raw_text)
    if len(cleaned_text) < 120:
        return None

    relative_path = path.relative_to(source_root)
    title = _normalize_title(extracted_title or path.stem)
    abstract = _extract_abstract(cleaned_text)
    keywords = _extract_keywords(cleaned_text)
    tags = _build_tags(relative_path, title, cleaned_text)
    applicable_products = _detect_keywords(title + "\n" + cleaned_text[:4000], PRODUCT_KEYWORDS)
    applicable_channels = _detect_keywords(title + "\n" + cleaned_text[:4000], CHANNEL_KEYWORDS)
    supported_questions = _detect_keywords(title + "\n" + cleaned_text[:5000], QUESTION_KEYWORDS)
    doc_id = _stable_id(str(relative_path))

    return RagDocument(
        doc_id=doc_id,
        title=title,
        source_path=str(relative_path).replace("\\", "/"),
        file_type=path.suffix.lower().lstrip("."),
        theme_path=_theme_path(relative_path),
        source_group=relative_path.parts[0] if relative_path.parts else "",
        tags=tags,
        applicable_products=applicable_products,
        applicable_channels=applicable_channels,
        supported_questions=supported_questions,
        abstract=abstract,
        keywords=keywords,
        full_text=cleaned_text,
        text_length=len(cleaned_text),
    )


def split_document_into_chunks(document: RagDocument, chunk_size: int = 780, overlap: int = 120) -> list[RagChunk]:
    paragraphs = [part.strip() for part in document.full_text.split("\n") if part.strip()]
    merged_blocks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 1 <= chunk_size:
            current = f"{current}\n{paragraph}".strip()
            continue
        if current:
            merged_blocks.append(current)
        if len(paragraph) <= chunk_size:
            current = paragraph
            continue
        start = 0
        while start < len(paragraph):
            block = paragraph[start:start + chunk_size]
            merged_blocks.append(block)
            start += max(chunk_size - overlap, 1)
        current = ""
    if current:
        merged_blocks.append(current)

    results: list[RagChunk] = []
    for index, block in enumerate(merged_blocks, start=1):
        results.append(
            RagChunk(
                chunk_id=f"{document.doc_id}-chunk-{index:03d}",
                doc_id=document.doc_id,
                title=document.title,
                sequence=index,
                text=block,
                text_length=len(block),
                theme_path=document.theme_path,
                tags=document.tags,
                is_conclusion_like=_is_conclusion_like(block),
            )
        )
    return results


def extract_insights(document: RagDocument, chunks: list[RagChunk]) -> list[RagInsight]:
    results: list[RagInsight] = []
    for chunk in chunks:
        sentences = _split_sentences(chunk.text)
        for sentence in sentences:
            normalized = sentence.strip()
            if len(normalized) < 24:
                continue
            insight_type = _classify_insight(normalized)
            if insight_type is None:
                continue
            insight_id = _stable_id(f"{chunk.chunk_id}:{normalized[:80]}")
            results.append(
                RagInsight(
                    insight_id=insight_id,
                    doc_id=document.doc_id,
                    title=document.title,
                    source_chunk_id=chunk.chunk_id,
                    text=normalized,
                    insight_type=insight_type,
                    theme_path=document.theme_path,
                    tags=document.tags,
                )
            )
    return results


def write_rag_corpus(
    documents: list[RagDocument],
    chunks: list[RagChunk],
    insights: list[RagInsight],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "documents.json").write_text(
        json.dumps([asdict(item) for item in documents], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_jsonl(output_dir / "chunks.jsonl", chunks)
    _write_jsonl(output_dir / "insights.jsonl", insights)
    summary = {
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "insight_count": len(insights),
        "source_groups": sorted({item.source_group for item in documents}),
        "themes": sorted({item.theme_path for item in documents}),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_jsonl(path: Path, items: Iterable[object]) -> None:
    lines = [json.dumps(asdict(item), ensure_ascii=False) for item in items]
    path.write_text("\n".join(lines), encoding="utf-8")


def _extract_raw_text(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf_text(path), ""
    if suffix in {".html", ".htm"}:
        return _extract_html_text(path)
    text = path.read_text(encoding="utf-8", errors="ignore")
    return text, ""


def _extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    texts: list[str] = []
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        if page_text.strip():
            texts.append(page_text)
    return "\n".join(texts)


def _extract_html_text(path: Path) -> tuple[str, str]:
    content = path.read_text(encoding="utf-8", errors="ignore")
    parser = _HtmlTextExtractor()
    parser.feed(content)
    return parser.text(), parser.title


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"首页\s*>\s*正文", "", text)
    text = re.sub(r"扫一扫在手机打开当前页", "", text)
    text = re.sub(r"版权所有.*", "", text)
    text = re.sub(r"联系电话[:：]?[0-9\-，,\s]+", "", text)
    text = re.sub(r"联系人[:：]?[^\n]{0,30}", "", text)
    text = re.sub(r"地址[:：]?[^\n]{0,80}", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t\u3000]{2,}", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[^\S\n]{2,}", " ", text)
    text = re.sub(r"(点击|收藏|打印|关闭窗口|返回顶部|汉斯出版社)$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _extract_abstract(text: str) -> str:
    patterns = [
        r"(摘要[:：].{40,800}?)\n(?:关键词|Key words|Abstract|1[\.、 ])",
        r"(Abstract[:：].{40,1200}?)\n(?:Key words|关键词|1[\.、 ])",
        r"(内容提要[:：].{40,800}?)\n(?:关键词|1[\.、 ])",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
        if match:
            return clean_text(match.group(1))
    first_lines = "\n".join(text.splitlines()[:8])
    return first_lines[:600].strip()


def _extract_keywords(text: str) -> list[str]:
    match = re.search(r"(关键词|Key words)[:：]\s*(.+)", text, flags=re.IGNORECASE)
    if not match:
        return []
    raw = match.group(2).split("\n", 1)[0]
    parts = re.split(r"[；;，,、 ]+", raw)
    return [part.strip() for part in parts if 1 < len(part.strip()) <= 20][:12]


def _build_tags(relative_path: Path, title: str, text: str) -> list[str]:
    tags: list[str] = []
    for part in relative_path.parts[:-1]:
        normalized = part.replace("_", " ").replace("-", " ").strip()
        if normalized and normalized not in tags:
            tags.append(normalized)
    for detected in _detect_keywords(title + "\n" + text[:5000], PRODUCT_KEYWORDS):
        if detected not in tags:
            tags.append(detected)
    for detected in _detect_keywords(title + "\n" + text[:5000], CHANNEL_KEYWORDS):
        if detected not in tags:
            tags.append(detected)
    return tags[:16]


def _detect_keywords(text: str, mapping: dict[str, str]) -> list[str]:
    results: list[str] = []
    for needle, label in mapping.items():
        if needle in text and label not in results:
            results.append(label)
    return results


def _theme_path(relative_path: Path) -> str:
    if len(relative_path.parts) <= 1:
        return relative_path.parts[0] if relative_path.parts else ""
    return "/".join(relative_path.parts[:-1]).replace("\\", "/")


def _normalize_title(title: str) -> str:
    title = clean_text(title)
    title = title.replace("_", " ").strip()
    return title or "未命名资料"


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？；;])", text)
    return [part.strip() for part in parts if part.strip()]


def _classify_insight(sentence: str) -> str | None:
    if any(marker in sentence for marker in ("联系电话", "联系人", "扫一扫", "版权所有", "机关子站", "直属单位网站")):
        return None
    if len(sentence) > 260:
        return None
    if any(marker in sentence for marker in ("建议", "对策", "启示")):
        return "strategy"
    if any(marker in sentence for marker in ("显著", "影响", "作用", "中介效应", "促进", "抑制")):
        return "finding"
    if any(marker in sentence for marker in ("研究表明", "研究发现", "结果表明", "结果显示", "实证")):
        return "conclusion"
    return None


def _is_conclusion_like(text: str) -> bool:
    return any(pattern in text for pattern in CONCLUSION_PATTERNS)


def _stable_id(seed: str) -> str:
    return hashlib.md5(seed.encode("utf-8")).hexdigest()[:16]
