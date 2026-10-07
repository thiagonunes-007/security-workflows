"""Converte Bíblias do scrollmapper (JSON) em línguas modernas e as alinha à Vulgata (comprimento + auditoria por nomes).

Presets: fr_lxx_giguet (La Septante, trad. P. Giguet, 1872 - só AT).
  curl -sSLO https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/FreLXXGiguet.json
Uso: python -m scripts.convert_aligned_bible fr_lxx_giguet FreLXXGiguet.json

Segue a numeração da LXX (como o Swete): Susana = Dn 13, Bel = Dn 14, Carta de Jeremias = Br 6. Livros fora
do cânon católico (1 Esdras, 3-4 Macabeus, Oração de Manassés, Sl 151, Odes, Enoque, Sl de Salomão) e a Oração de
Azarias são omitidos. Pares não sustentados pela auditoria saem sem canon_ref.
"""
import hashlib
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from ckb.align import classify_book
from ckb.schema import CKB_DIR
from ckb.verify import filter_alignments
from scripts.convert_scrollmapper_bible import BOOKS, OSIS

OSIS_TO_NAME = {osis: name for name, osis in OSIS.items()}
OSIS_TO_ABBR = {osis: BOOKS[name] for name, osis in OSIS.items()}
BASE_URL = "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/"
PRESETS = {
    "fr_lxx_giguet": {
        "language": "fr", "file": "FreLXXGiguet.json", "max_psalm": 150,
        "license_note": "Trad. de Pierre Giguet (1872), domínio público por idade; só AT; numeração da LXX.",
    },
}
# livro do arquivo -> (osis, capítulo fixo ou None)
EXTRA = {"Susanna": ("Dan", 13), "Bel and the Dragon": ("Dan", 14), "Epistle of Jeremiah": ("Bar", 6)}


def letters(t: str) -> int:
    return sum(1 for c in t if c.isalpha())


def collect(data: dict, max_psalm: int) -> dict[str, list[tuple[int, int, str]]]:
    books: dict[str, list] = {}
    for b in data["books"]:
        name = b["name"]
        if name in EXTRA:
            osis, fixed = EXTRA[name]
        elif name in OSIS:
            osis, fixed = OSIS[name], None
        else:
            continue
        for ch in b["chapters"]:
            if osis == "Ps" and ch["chapter"] > max_psalm:
                continue
            for v in ch["verses"]:
                text = " ".join(v["text"].split())
                if text:
                    books.setdefault(osis, []).append((fixed or ch["chapter"], v["verse"], text))
    for osis in books:
        books[osis].sort(key=lambda x: (x[0], x[1]))
    return books


def main(preset_name: str, path: str) -> None:
    preset = PRESETS[preset_name]
    raw = Path(path).read_bytes()
    books = collect(json.loads(raw), preset["max_psalm"])
    latin, latin_text = {}, {}
    for line in (CKB_DIR / "corpus" / "vulgata_clementina.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        b, c, v = r["canon_ref"].split(".")
        latin.setdefault(b, []).append(((int(c), int(v)), letters(r["text"])))
        latin_text[r["canon_ref"]] = r["text"]
    rows, quality = [], {}
    for osis, verses in books.items():
        if osis not in latin:
            continue
        res, qs = classify_book([(c, v) for c, v, _ in verses], [letters(t) for _, _, t in verses], latin[osis])
        quality[osis] = qs
        for (c, v, text), a in zip(verses, res):
            refs = [f"{osis}.{cc}.{vv}" for cc, vv in a["refs"]]
            rows.append({
                "source_id": preset_name, "canon_ref": refs[0] if refs else "",
                "canon_ref_2": refs[1] if len(refs) > 1 else "", "align": a["label"],
                "ref": f"{OSIS_TO_ABBR[osis]} {c},{v}", "text": text,
                "section": f"{OSIS_TO_NAME[osis]} {c}", "language": preset["language"],
            })
    rows, filt = filter_alignments(rows, latin_text, script="latin")
    counts = Counter(r["align"] or "sem-par" for r in rows)
    out = CKB_DIR / "corpus" / f"{preset_name}.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    prov = {
        "source_id": preset_name, "converted_on": date.today().isoformat(), "input_url": BASE_URL + preset["file"],
        "input_sha256": hashlib.sha256(raw).hexdigest(), "passages": len(rows), "books_present": len(quality),
        "books_missing": sorted(set(latin) - set(quality)), "alignment_totals": dict(counts),
        "alignment_quality": quality, "name_audit_filter": filt, "license_note": preset["license_note"],
    }
    out.with_suffix(".provenance.json").write_text(json.dumps(prov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{preset_name}: {len(rows)} versículos | livros {len(quality)} | alinhamento {dict(counts)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
