"""Converte o grego para o CKB e o alinha à Vulgata: NT Byzantine (Robinson-Pierpont) e AT Septuaginta (Swete).

Fontes (baixe/clone antes):
  NT : github.com/byztxt/byzantine-majority-text  -> csv-unicode/ccat/no-variants/*.csv  (domínio público)
  AT : github.com/OpenGreekAndLatin/First1KGreek  -> data/tlg0527/tlg0NN/*.1st1K-grc1.xml (CC BY-SA 4.0)
Requer ckb/corpus/vulgata_clementina.jsonl.
Uso: python -m scripts.convert_greek byz  PASTA_COM_CSV
     python -m scripts.convert_greek lxx  PASTA_COM_XML_DO_SWETE

Alinhamento: ckb.align.classify_book (comprimento) + auditoria por nomes próprios (ckb.verify) que REMOVE
pares não sustentados; TRAVA DE QUALIDADE — livros em que mais de 40% dos
versículos ficam em regiões não 1:1 (ordem/versificação da LXX difere da Vulgata) saem SEM canon_ref.
Daniel usa Teodócion (+ Susana = Dn 13, Bel = Dn 14); Baruc inclui a Carta de Jeremias como cap. 6;
Esdras II (tlg018) é dividido em Esdras (1-10) e Neemias (11-23 -> 1-13).
"""
import hashlib
import html
import json
import re
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

BYZ_FILES = {
    "MAT": "Matt", "MAR": "Mark", "LUK": "Luke", "JOH": "John", "ACT": "Acts", "ROM": "Rom", "1CO": "1Cor",
    "2CO": "2Cor", "GAL": "Gal", "EPH": "Eph", "PHP": "Phil", "COL": "Col", "1TH": "1Thess", "2TH": "2Thess",
    "1TI": "1Tim", "2TI": "2Tim", "TIT": "Titus", "PHM": "Phlm", "HEB": "Heb", "JAM": "Jas", "1PE": "1Pet",
    "2PE": "2Pet", "1JO": "1John", "2JO": "2John", "3JO": "3John", "JUD": "Jude", "REV": "Rev",
}
# osis -> [(tlg, deslocamento_de_capitulo, capítulo_fixo|None)]
LXX_WORKS = {
    "Gen": ["001"], "Exod": ["002"], "Lev": ["003"], "Num": ["004"], "Deut": ["005"], "Josh": ["006"],
    "Judg": ["008"], "Ruth": ["010"], "1Sam": ["011"], "2Sam": ["012"], "1Kgs": ["013"], "2Kgs": ["014"],
    "1Chr": ["015"], "2Chr": ["016"], "Ezra": ["018:1-10"], "Neh": ["018:11-23"], "Esth": ["019"],
    "Jdt": ["020"], "Tob": ["021"], "1Macc": ["023"], "2Macc": ["024"], "Ps": ["027:1-150"], "Prov": ["029"],
    "Eccl": ["030"], "Song": ["031"], "Job": ["032"], "Wis": ["033"], "Sir": ["034"], "Hos": ["036"],
    "Amos": ["037"], "Mic": ["038"], "Joel": ["039"], "Obad": ["040"], "Jonah": ["041"], "Nah": ["042"],
    "Hab": ["043"], "Zeph": ["044"], "Hag": ["045"], "Zech": ["046"], "Mal": ["047"], "Isa": ["048"],
    "Jer": ["049"], "Bar": ["050", "052@6"], "Lam": ["051"], "Ezek": ["053"],
    "Dan": ["057", "055@13", "059@14"],
}
_NOTE = re.compile(r"<note\b.*?</note>", re.S)
_TAG = re.compile(r"<[^>]+>")


def clean(t: str) -> str:
    t = html.unescape(_TAG.sub("", _NOTE.sub("", t))).replace("¶", "")
    return " ".join(t.split())


def letters(t: str) -> int:
    return sum(1 for c in t if c.isalpha())


def read_byz(path: Path) -> list[tuple[int, int, str]]:
    import csv

    out = []
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            text = clean(row["text"])
            if text:
                out.append((int(row["chapter"]), int(row["verse"]), text))
    return out


def read_swete(path: Path, fixed_chapter: int | None = None) -> list[tuple[int, int, str]]:
    x = path.read_text(encoding="utf-8")
    out, chap = [], None
    for m in re.finditer(r'<div type="textpart" subtype="(chapter|verse)" n="([^"]*)"[^>]*>|</div>', x):
        pass
    # percorre capítulos e versículos em ordem de documento
    pat = re.compile(
        r'<div type="textpart" subtype="chapter" n="([^"]*)"|'
        r'<div type="textpart" subtype="verse" n="([^"]*)"[^>]*>(.*?)</div>', re.S)
    for m in pat.finditer(x):
        if m.group(1) is not None:
            chap = int(m.group(1)) if m.group(1).isdigit() else 0
        else:
            n = m.group(2)
            if not n.isdigit():
                continue
            text = clean(m.group(3))
            c = fixed_chapter if fixed_chapter is not None else (chap if chap is not None else 1)
            if text:
                out.append((c, int(n), text))
    return out


def load_latin() -> dict[str, list]:
    out: dict[str, list] = {}
    for line in (CKB_DIR / "corpus" / "vulgata_clementina.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        b, c, v = r["canon_ref"].split(".")
        out.setdefault(b, []).append(((int(c), int(v)), letters(r["text"])))
    return out


def lxx_work(folder: Path, osis: str, spec: list[str]) -> list[tuple[int, int, str]]:
    verses = []
    for part in spec:
        fixed = None
        if "@" in part:
            part, fx = part.split("@")
            fixed = int(fx)
        rng = None
        if ":" in part:
            part, r = part.split(":")
            lo, hi = r.split("-")
            rng = (int(lo), int(hi))
        f = folder / f"tlg0527.tlg{part}.1st1K-grc1.xml"
        if not f.exists():
            continue
        for c, v, t in read_swete(f, fixed):
            if rng and not rng[0] <= c <= rng[1]:
                continue
            if osis == "Neh":
                c -= 10
            verses.append((c, v, t))
    return verses


def emit(source_id, language, books, latin, structural_rows=None):
    rows, quality, counts = [], {}, Counter()
    for osis, verses in books.items():
        if not verses:
            continue
        res, qs = classify_book([(c, v) for c, v, _ in verses], [letters(t) for _, _, t in verses], latin[osis])
        quality[osis] = qs
        for (c, v, text), a in zip(verses, res):
            refs = [f"{osis}.{cc}.{vv}" for cc, vv in a["refs"]]
            rows.append({
                "source_id": source_id, "canon_ref": refs[0] if refs else "",
                "canon_ref_2": refs[1] if len(refs) > 1 else "", "align": a["label"],
                "ref": f"{OSIS_TO_ABBR[osis]} {c},{v}", "text": text,
                "section": f"{OSIS_TO_NAME[osis]} {c}", "language": language,
            })
            counts[a["label"] or "sem-par"] += 1
    return rows, quality, counts


def main(mode: str, folder: str) -> None:
    folder_p, latin = Path(folder), load_latin()
    sha = hashlib.sha256()
    if mode == "byz":
        sid, books = "byz_nt", {}
        for code, osis in BYZ_FILES.items():
            raw = (folder_p / f"{code}.csv").read_bytes()
            sha.update(raw)
            books[osis] = read_byz(folder_p / f"{code}.csv")
        license_note = "Byzantine Textform (Robinson-Pierpont): domínio público (LICENSE.txt do repositório byztxt)."
        url = "https://github.com/byztxt/byzantine-majority-text/tree/master/csv-unicode/ccat/no-variants"
    else:
        sid, books = "lxx_swete", {}
        for osis, spec in LXX_WORKS.items():
            books[osis] = lxx_work(folder_p, osis, spec)
            for part in spec:
                f = folder_p / f"tlg0527.tlg{part.split(':')[0].split('@')[0]}.1st1K-grc1.xml"
                if f.exists():
                    sha.update(f.read_bytes())
        license_note = ("Septuaginta (Swete, 1901) transcrita pelo First1KGreek/Open Greek and Latin: "
                        "CC BY-SA 4.0 - atribuição obrigatória; derivados sob a mesma licença.")
        url = "https://github.com/OpenGreekAndLatin/First1KGreek/tree/master/data/tlg0527"
    rows, quality, counts = emit(sid, "grc", books, latin)
    latin_text = {json.loads(l)["canon_ref"]: json.loads(l)["text"]
                  for l in (CKB_DIR / "corpus" / "vulgata_clementina.jsonl").read_text(encoding="utf-8").splitlines()}
    rows, filt = filter_alignments(rows, latin_text)  # auditoria independente por nomes próprios
    counts = Counter(r["align"] or "sem-par" for r in rows)
    out = CKB_DIR / "corpus" / f"{sid}.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    absent = sorted(o for o, v in books.items() if not v)
    unaligned = sorted(o for o, q in quality.items() if not q["aligned"])
    prov = {
        "source_id": sid, "converted_on": date.today().isoformat(), "input_url": url,
        "input_sha256_of_concatenated_files": sha.hexdigest(), "passages": len(rows),
        "books_present": len(quality), "books_absent_from_download": absent,
        "books_without_alignment_quality_gate": unaligned, "alignment_totals": dict(counts),
        "alignment_quality": quality, "name_audit_filter": filt, "license_note": license_note,
    }
    out.with_suffix(".provenance.json").write_text(json.dumps(prov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{sid}: {len(rows)} versículos | livros {len(quality)} | ausentes {absent} | sem alinhamento {unaligned}")
    print(dict(counts))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
