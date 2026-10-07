"""Converte o Westminster Leningrad Codex (OSHB, 39 livros) para o CKB, alinhado à Vulgata.

Entrada: pasta com os XML do repositório openscriptures/morphhb (diretório wlc/):
  for b in Gen Exod Lev Num Deut Josh Judg Ruth 1Sam 2Sam 1Kgs 2Kgs 1Chr 2Chr Ezra Neh Esth Job Ps \\
           Prov Eccl Song Isa Jer Lam Ezek Dan Hos Joel Amos Obad Jonah Mic Nah Hab Zeph Hag Zech Mal; do
    curl -sSLO https://raw.githubusercontent.com/openscriptures/morphhb/master/wlc/$b.xml; done
Requer ckb/corpus/vulgata_clementina.jsonl (rode antes scripts.convert_scrollmapper_bible).
Uso: python -m scripts.convert_oshb_hebrew PASTA_COM_XML

- ref = citação na numeração HEBRAICA (Sl 23,1); canon_ref = numeração da Vulgata (Ps.22.1).
- Salmos: ckb.psalms (tabela verificada). Ester e Daniel: ckb.books_map (regra estrutural).
  Demais livros: alinhamento por comprimento (ckb.align),
  com rótulo de qualidade em `align`: identico | deslocado | incerto. Sem par = canon_ref vazio.
- Texto: palavras do OSHB sem marcação de morfemas ('/'), ketiv no corpo (qere/variantes em <note>
  são descartados), maqaf e sof pasuq preservados. Só protocanônicos (39 livros).
"""
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

from ckb.align import classify_book
from ckb.books_map import STRUCTURAL
from ckb.psalms import hebrew_to_vulgate
from ckb.schema import CKB_DIR
from scripts.convert_scrollmapper_bible import BOOKS, OSIS

SOURCE_ID = "wlc_hebrew"
SOURCE_URL = "https://raw.githubusercontent.com/openscriptures/morphhb/master/wlc/"
OSHB_BOOKS = [
    "Gen", "Exod", "Lev", "Num", "Deut", "Josh", "Judg", "Ruth", "1Sam", "2Sam", "1Kgs", "2Kgs",
    "1Chr", "2Chr", "Ezra", "Neh", "Esth", "Job", "Ps", "Prov", "Eccl", "Song", "Isa", "Jer", "Lam",
    "Ezek", "Dan", "Hos", "Joel", "Amos", "Obad", "Jonah", "Mic", "Nah", "Hab", "Zeph", "Hag", "Zech", "Mal",
]
OSIS_TO_NAME = {osis: name for name, osis in OSIS.items()}
OSIS_TO_ABBR = {osis: BOOKS[name] for name, osis in OSIS.items()}
assert all(b in OSIS_TO_NAME for b in OSHB_BOOKS)

MAQAF, SOF_PASUQ, PASEQ = "־", "׃", "׀"
_WRAP = re.compile(r'<seg type="x-(?:small|large|reversednun|suspended)"[^>]*>(.*?)</seg>', re.S)
_TOKEN = re.compile(r'<w[^>]*>(?P<w>.*?)</w>|<seg type="(?P<seg>[^"]+)"[^>]*>', re.S)
_VERSE = re.compile(r'<verse osisID="(?P<b>[^."]+)\.(?P<c>\d+)\.(?P<v>\d+)">(?P<body>.*?)</verse>', re.S)


def verse_text(body: str) -> str:
    body = re.sub(r"<note\b.*?</note>", "", body, flags=re.S)  # qere/variantes/notas
    body = _WRAP.sub(r"\1", body)
    out, glue = "", True
    for m in _TOKEN.finditer(body):
        if m.group("w") is not None:
            w = re.sub(r"<[^>]+>", "", m.group("w")).replace("/", "")
            out += w if glue else " " + w
            glue = False
        else:
            seg = m.group("seg")
            if seg == "x-maqqef":
                out += MAQAF
                glue = True  # a próxima palavra cola
            elif seg == "x-sof-pasuq":
                out += SOF_PASUQ
            elif seg == "x-paseq":
                out += " " + PASEQ
            # x-pe / x-samekh: marcas de parágrafo, ignoradas
    return unicodedata.normalize("NFC", out.strip())


def read_book(path: Path) -> list[tuple[int, int, str]]:
    xml = path.read_text(encoding="utf-8")
    return [(int(m["c"]), int(m["v"]), verse_text(m["body"])) for m in _VERSE.finditer(xml)]


def letters(text: str) -> int:
    return sum(1 for c in unicodedata.normalize("NFD", text) if "א" <= c <= "ת")


def load_latin() -> dict[str, list[tuple[tuple[int, int], int]]]:
    """livro OSIS -> [((cap, vers), nº de letras)] na ordem do corpus."""
    out: dict[str, list] = {}
    for line in (CKB_DIR / "corpus" / "vulgata_clementina.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        b, c, v = r["canon_ref"].split(".")
        out.setdefault(b, []).append(((int(c), int(v)), len(re.sub(r"\W", "", r["text"]))))
    return out


def classify(verses, lat) -> tuple[list[dict], dict]:
    """Alinha um livro (não-Salmos) à Vulgata; ver ckb.align.classify_book."""
    return classify_book([(c, v) for c, v, _ in verses], [letters(t) for _, _, t in verses], lat)


def main(folder: str) -> None:
    folder_p, latin = Path(folder), load_latin()
    rows, stats, missing, sha = [], {}, [], hashlib.sha256()
    quality = {}
    for b in OSHB_BOOKS:
        raw = (folder_p / f"{b}.xml").read_bytes()
        sha.update(raw)
        verses = read_book(folder_p / f"{b}.xml")
        abbr = OSIS_TO_ABBR[b]
        if b == "Ps":
            res = []
            for c, v, _ in verses:
                r = hebrew_to_vulgate(c, v)
                res.append({"refs": [(r.chapter, x) for x in r.verses][:2], "label": f"psalmos-{r.confidence}"})
        elif b in STRUCTURAL:  # Ester/Daniel: acréscimos gregos, regra estrutural
            res = [{"refs": [STRUCTURAL[b](c, v)], "label": "estrutural"} for c, v, _ in verses]
        else:
            res, qs = classify(verses, latin[b])
            quality[b] = qs
        for (c, v, text), a in zip(verses, res):
            if not text:
                missing.append(f"{abbr} {c},{v}")
                continue
            refs = [f"{b}.{cc}.{vv}" for cc, vv in a["refs"]]
            rows.append({
                "source_id": SOURCE_ID,
                "canon_ref": refs[0] if refs else "",
                "canon_ref_2": refs[1] if len(refs) > 1 else "",
                "align": a["label"],
                "ref": f"{abbr} {c},{v}",
                "text": text,
                "section": f"{OSIS_TO_NAME[b]} {c}" + (" (numeração hebraica)" if b == "Ps" else ""),
                "language": "hbo",
            })
        stats[b] = dict(Counter(a["label"] or "sem-par" for a in res))
    out = CKB_DIR / "corpus" / f"{SOURCE_ID}.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    total = Counter(r["align"] or "sem-par" for r in rows)
    prov = {
        "source_id": SOURCE_ID, "converted_on": date.today().isoformat(), "input_url": SOURCE_URL,
        "input_sha256_of_concatenated_books": sha.hexdigest(), "books": len(OSHB_BOOKS),
        "passages": len(rows), "alignment_totals": dict(total), "alignment_by_book": stats, "alignment_quality": quality,
        "empty_verses_in_input": missing,
        "license_note": "Texto do WLC em domínio público; lematização/morfologia (não usadas) CC BY 4.0 (OSHB).",
    }
    out.with_suffix(".provenance.json").write_text(json.dumps(prov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(rows)} versículos → {out}\nalinhamento: {dict(total)}")


if __name__ == "__main__":
    main(sys.argv[1])
