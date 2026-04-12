from __future__ import annotations

import json
import sys
from pathlib import Path

from app.rag_answer import build_llm_strategy_analysis


def main() -> None:
    product_id = sys.argv[1] if len(sys.argv) > 1 else "P002"
    result = build_llm_strategy_analysis(product_id)
    payload = json.dumps(result.model_dump(), ensure_ascii=False, indent=2)
    output_path = Path(__file__).resolve().parent / "mock_data" / "rag_corpus" / f"preview_strategy_{product_id}.json"
    output_path.write_text(payload, encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
