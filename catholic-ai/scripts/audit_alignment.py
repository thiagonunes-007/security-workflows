"""Audita alinhamentos grego<->latim por nomes próprios (ckb.verify). Uso: python -m scripts.audit_alignment byz_nt"""
import json
import sys
from collections import defaultdict

from ckb.schema import CKB_DIR
from ckb.verify import agrees


def audit(source_id: str):
    lat = {}
    for line in (CKB_DIR / "corpus" / "vulgata_clementina.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        lat[r["canon_ref"]] = r["text"]
    stat = defaultdict(lambda: defaultdict(lambda: [0, 0]))  # livro -> rótulo -> [ok, com_sinal]
    for line in (CKB_DIR / "corpus" / f"{source_id}.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if not r["canon_ref"] or r["canon_ref"] not in lat:
            continue
        a = agrees(r["text"], lat[r["canon_ref"]] + (" " + lat.get(r["canon_ref_2"], "") if r["canon_ref_2"] else ""))
        if a is None:
            continue
        book = r["canon_ref"].split(".")[0]
        s = stat[book][r["align"]]
        s[0] += a
        s[1] += 1
    return stat


if __name__ == "__main__":
    st = audit(sys.argv[1])
    for book, labels in sorted(st.items()):
        tot = [sum(v[0] for v in labels.values()), sum(v[1] for v in labels.values())]
        print(f"{book:6} geral {tot[0]/tot[1]:.2f} ({tot[1]:4}) | " + " ".join(
            f"{l or '-'}:{v[0]/v[1]:.2f}({v[1]})" for l, v in sorted(labels.items())))
