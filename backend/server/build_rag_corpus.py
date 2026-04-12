from __future__ import annotations

from pathlib import Path

from app.rag_ingest import build_rag_corpus, write_rag_corpus


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "rag_materials"
OUTPUT_ROOT = Path(__file__).resolve().parent / "mock_data" / "rag_corpus"


def main() -> None:
    documents, chunks, insights = build_rag_corpus(SOURCE_ROOT)
    write_rag_corpus(documents, chunks, insights, OUTPUT_ROOT)
    print(
        "rag-corpus-built:",
        f"documents={len(documents)}",
        f"chunks={len(chunks)}",
        f"insights={len(insights)}",
    )


if __name__ == "__main__":
    main()
