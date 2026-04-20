from __future__ import annotations

import json
import sys

from app.rag_search import search_rag


def main() -> None:
    query = sys.argv[1] if len(sys.argv) > 1 else "地理标志 如何提升购买意愿"
    result = search_rag(query, top_k=5)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
