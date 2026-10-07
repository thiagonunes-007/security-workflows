"""Ingere fontes do CKB no banco vetorial, SOMENTE se a licença permitir.

Uso: python -m scripts.ingest vulgata_clementina douay_rheims
"""
import hashlib
import sys

from app.config import get_settings
from app.rag import get_collection
from ckb.languages import normalize_for_search
from ckb.schema import load_passages, load_registry


def main(source_ids: list[str]) -> None:
    reg = load_registry()
    col = get_collection(get_settings())
    for sid in source_ids:
        src = reg.get(sid)
        if src is None:
            raise SystemExit(f"fonte desconhecida: {sid}")
        if not src.ingestable:
            raise SystemExit(f"{sid}: licença '{src.license_status}' — ingestão bloqueada")
        ps = load_passages(sid)
        norm = [normalize_for_search(p.text, src.language) for p in ps]
        metas = []
        for p, n in zip(ps, norm):
            m = {"ref": p.ref, "source": src.title, "authority": src.authority,
                 "language": src.language, "section": p.section, "canon_ref": p.canon_ref,
                 "canon_ref_2": p.canon_ref_2, "align": p.align}
            if n != p.text:  # hebraico/grego: indexa normalizado, guarda o original p/ exibir
                m["original"] = p.text
            metas.append(m)
        col.upsert(
            ids=[hashlib.sha1(f"{p.source_id}|{p.ref}".encode()).hexdigest() for p in ps],
            documents=norm,
            metadatas=metas,
        )
        print(f"{sid}: {len(ps)} trechos")


if __name__ == "__main__":
    main(sys.argv[1:])
