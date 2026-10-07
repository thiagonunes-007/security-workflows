"""Converte a Bíblia de Allioli (alemão, tradução católica da Vulgata, ed. 1914) para o CKB.

Fonte: github.com/AlexBocken/allioli (arquivo allioli.tsv):
  curl -sSLO https://raw.githubusercontent.com/AlexBocken/allioli/master/allioli.tsv
Uso: python -m scripts.convert_allioli_german allioli.tsv

- Usa só a coluna alemã. O latim do TSV perdeu ligaduras ("clum") — o latim do CKB vem da Clementina.
- Allioli segue a numeração da Vulgata, logo canon_ref = (livro, cap., vers.) direto, conferido contra o
  latim do CKB. Notas de rodapé, números sobrescritos e a lista de paralelos "[Sl 32,6, ...]" saem do texto.
- O TSV cobre 68 dos 73 livros (faltam 1-2 Reis, Esdras, Romanos, Hebreus); a lista vai no provenance.
"""
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from ckb.schema import CKB_DIR
from scripts.convert_scrollmapper_bible import BOOKS, OSIS

SOURCE_ID = "allioli_de"
SOURCE_URL = "https://raw.githubusercontent.com/AlexBocken/allioli/master/allioli.tsv"
ABBR_TO_OSIS = {
    "Gen": "Gen", "Ex": "Exod", "Lev": "Lev", "Num": "Num", "Dtn": "Deut", "Jos": "Josh", "Ri": "Judg",
    "Rut": "Ruth", "1Sam": "1Sam", "2Sam": "2Sam", "1Chr": "1Chr", "2Chr": "2Chr", "Neh": "Neh",
    "Tob": "Tob", "Jdt": "Jdt", "Est": "Esth", "1Makk": "1Macc", "2Makk": "2Macc", "Ijob": "Job",
    "Ps": "Ps", "Spr": "Prov", "Koh": "Eccl", "Hld": "Song", "Weish": "Wis", "Sir": "Sir", "Jes": "Isa",
    "Jer": "Jer", "Klgl": "Lam", "Bar": "Bar", "Ez": "Ezek", "Dan": "Dan", "Hos": "Hos", "Joel": "Joel",
    "Am": "Amos", "Obd": "Obad", "Jona": "Jonah", "Mi": "Mic", "Nah": "Nah", "Hab": "Hab", "Zef": "Zeph",
    "Hag": "Hag", "Sach": "Zech", "Mal": "Mal", "Mt": "Matt", "Mk": "Mark", "Lk": "Luke", "Apg": "Acts",
    "Joh": "John", "1Kor": "1Cor", "Gal": "Gal", "2Kor": "2Cor", "Eph": "Eph", "Phil": "Phil",
    "1Thess": "1Thess", "Kol": "Col", "2Thess": "2Thess", "1Tim": "1Tim", "Tit": "Titus", "2Tim": "2Tim",
    "Phlm": "Phlm", "Jak": "Jas", "1Petr": "1Pet", "2Petr": "2Pet", "1Joh": "1John", "2Joh": "2John",
    "3Joh": "3John", "Jud": "Jude", "Offb": "Rev",
}
OSIS_TO_NAME = {osis: name for name, osis in OSIS.items()}
OSIS_TO_ABBR = {osis: BOOKS[name] for name, osis in OSIS.items()}
_SUPER = re.compile("[¹²³⁰-⁹]+")
_PARALLELS = re.compile(r"\s*\[[^\[\]]*\d[^\[\]]*\]")  # "[Ps 32,6, Ps 135,5]": paralelos (todos os 153 colchetes da fonte)


def clean(text: str) -> str:
    text = _SUPER.sub("", text)
    text = _PARALLELS.sub("\x00", text)
    text = re.sub(r"([.!?;:,])\x00\.", r"\1", text)  # "Zahn. [Lev 24,20]." -> "Zahn."
    return " ".join(text.replace("\x00", "").split())


def parse(tsv: str) -> list[tuple[str, int, int, str]]:
    """Linhas de versículo: 7 campos, latim (col. 5) preenchido, versículo numérico."""
    out = []
    for line in tsv.splitlines():
        f = line.split("\t")
        if len(f) == 7 and f[5] and f[3].isdigit() and f[4].isdigit() and f[1] in ABBR_TO_OSIS:
            text = clean(f[6])
            if text:
                out.append((ABBR_TO_OSIS[f[1]], int(f[3]), int(f[4]), text))
    return out


def main(path: str) -> None:
    raw = Path(path).read_bytes()
    verses = parse(raw.decode("utf-8"))
    latin = set()
    for line in (CKB_DIR / "corpus" / "vulgata_clementina.jsonl").read_text(encoding="utf-8").splitlines():
        latin.add(json.loads(line)["canon_ref"])
    rows, seen, orphans = [], Counter(), []
    for osis, c, v, text in verses:
        canon = f"{osis}.{c}.{v}"
        ref = f"{OSIS_TO_ABBR[osis]} {c},{v}"
        seen[ref] += 1
        if seen[ref] > 1:
            continue  # linha duplicada na fonte
        if canon not in latin:
            orphans.append(ref)
        rows.append({
            "source_id": SOURCE_ID, "canon_ref": canon if canon in latin else "",
            "align": "identico" if canon in latin else "", "ref": ref, "text": text,
            "section": f"{OSIS_TO_NAME[osis]} {c}" + (" (numeração da Vulgata)" if osis == "Ps" else ""),
            "language": "de",
        })
    present = {r["canon_ref"].split(".")[0] for r in rows if r["canon_ref"]}
    missing_books = sorted({OSIS[n] for n in BOOKS} - present)
    covered = {r["canon_ref"] for r in rows if r["canon_ref"]}
    out = CKB_DIR / "corpus" / f"{SOURCE_ID}.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    prov = {
        "source_id": SOURCE_ID, "converted_on": date.today().isoformat(), "input_url": SOURCE_URL,
        "input_sha256": hashlib.sha256(raw).hexdigest(), "passages": len(rows),
        "books_present": len(present), "books_missing_in_source": missing_books,
        "verses_without_latin_counterpart": orphans[:200], "latin_verses_without_german": len(latin - covered),
        "duplicates_skipped": sum(n - 1 for n in seen.values() if n > 1),
        "license_note": "Allioli (+1873), ed. 1914: domínio público por idade; TSV de AlexBocken/allioli (Unlicense).",
    }
    out.with_suffix(".provenance.json").write_text(json.dumps(prov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(rows)} versículos | livros {len(present)}/73 | faltam {missing_books}")
    print(f"sem par latino: {len(orphans)} | latinos sem alemão: {len(latin - covered)}")


if __name__ == "__main__":
    main(sys.argv[1])
