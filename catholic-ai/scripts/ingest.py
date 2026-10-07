"""Ingere fontes em JSONL no banco vetorial.

Cada linha: {"text": "...", "ref": "Jo 3,16", "source": "Bíblia (ARC)", "authority": "escritura"}
Uso: python -m scripts.ingest data/sample/biblia_exemplo.jsonl
"""
import hashlib
import json
import sys

from app.config import get_settings
from app.rag import get_collection

REQUIRED = {"text", "ref", "source"}


def main(paths: list[str]) -> None:
    col = get_collection(get_settings())
    for path in paths:
        ids, docs, metas = [], [], []
        with open(path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                missing = REQUIRED - row.keys()
                if missing:
                    raise ValueError(f"{path}:{n} faltam campos {missing}")
                ids.append(hashlib.sha1(f"{row['source']}|{row['ref']}".encode()).hexdigest())
                docs.append(row["text"])
                metas.append({k: row.get(k, "") for k in ("ref", "source", "authority")})
        col.upsert(ids=ids, documents=docs, metadatas=metas)
        print(f"{path}: {len(ids)} trechos")


if __name__ == "__main__":
    main(sys.argv[1:])
