"""Converte a Bíblia Douay-Rheims (Challoner) para o formato do CKB.

Entrada: JSON do scrollmapper/bible_databases (formats/json/DRC.json):
  curl -sSLO https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/DRC.json
Saída: ckb/corpus/douay_rheims.jsonl + ckb/corpus/douay_rheims.provenance.json

Uso: python -m scripts.convert_douay_rheims DRC.json [--window N]

- Mantém só os 73 livros do cânon católico (descarta Oração de Manassés, 1-2 Esdras apócrifos,
  Salmo adicional e Laodicenses, presentes no arquivo mas fora do cânon de Trento).
- Referências em abreviaturas da Bíblia em português (Jo 3,16). Salmos seguem a numeração da
  Vulgata (usada pelo Douay-Rheims), que difere da hebraica em muitos salmos.
- --window N agrupa N versículos consecutivos do mesmo capítulo ("Jo 3,16-19"). Padrão 1 (um
  versículo por trecho, citação exata). Teste com o conjunto de avaliação antes de mudar.
"""
import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path

from ckb.schema import CKB_DIR

SOURCE_ID = "douay_rheims"
SOURCE_URL = "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/DRC.json"

# nome no arquivo -> (abreviatura pt-BR, nome)
BOOKS = {
    "Genesis": "Gn", "Exodus": "Ex", "Leviticus": "Lv", "Numbers": "Nm", "Deuteronomy": "Dt",
    "Joshua": "Js", "Judges": "Jz", "Ruth": "Rt", "I Samuel": "1Sm", "II Samuel": "2Sm",
    "I Kings": "1Rs", "II Kings": "2Rs", "I Chronicles": "1Cr", "II Chronicles": "2Cr",
    "Ezra": "Esd", "Nehemiah": "Ne", "Tobit": "Tb", "Judith": "Jt", "Esther": "Est", "Job": "Jó",
    "Psalms": "Sl", "Proverbs": "Pr", "Ecclesiastes": "Ecl", "Song of Solomon": "Ct",
    "Wisdom": "Sb", "Sirach": "Eclo", "Isaiah": "Is", "Jeremiah": "Jr", "Lamentations": "Lm",
    "Baruch": "Br", "Ezekiel": "Ez", "Daniel": "Dn", "Hosea": "Os", "Joel": "Jl", "Amos": "Am",
    "Obadiah": "Ab", "Jonah": "Jn", "Micah": "Mq", "Nahum": "Na", "Habakkuk": "Hab",
    "Zephaniah": "Sf", "Haggai": "Ag", "Zechariah": "Zc", "Malachi": "Ml",
    "I Maccabees": "1Mc", "II Maccabees": "2Mc", "Matthew": "Mt", "Mark": "Mc", "Luke": "Lc",
    "John": "Jo", "Acts": "At", "Romans": "Rm", "I Corinthians": "1Cor", "II Corinthians": "2Cor",
    "Galatians": "Gl", "Ephesians": "Ef", "Philippians": "Fl", "Colossians": "Cl",
    "I Thessalonians": "1Ts", "II Thessalonians": "2Ts", "I Timothy": "1Tm", "II Timothy": "2Tm",
    "Titus": "Tt", "Philemon": "Fm", "Hebrews": "Hb", "James": "Tg", "I Peter": "1Pd",
    "II Peter": "2Pd", "I John": "1Jo", "II John": "2Jo", "III John": "3Jo", "Jude": "Jd",
    "Revelation of John": "Ap",
}
assert len(BOOKS) == 73


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def convert(data: dict, window: int = 1) -> tuple[list[dict], list[str]]:
    rows, gaps, seen_books = [], [], set()
    for book in data["books"]:
        abbr = BOOKS.get(book["name"])
        if abbr is None:
            continue  # fora do cânon católico
        seen_books.add(book["name"])
        for ch in book["chapters"]:
            verses = []
            for v in ch["verses"]:
                text = clean(v["text"])
                if not text:
                    gaps.append(f"{abbr} {ch['chapter']},{v['verse']}")
                    continue
                verses.append((v["verse"], text))
            for i in range(0, len(verses), window):
                grp = verses[i : i + window]
                first, last = grp[0][0], grp[-1][0]
                span = f"{first}" if first == last else f"{first}-{last}"
                rows.append(
                    {
                        "source_id": SOURCE_ID,
                        "ref": f"{abbr} {ch['chapter']},{span}",
                        "text": " ".join(t for _, t in grp),
                        "section": f"{book['name']} {ch['chapter']}"
                        + (" (numeração da Vulgata)" if abbr == "Sl" else ""),
                        "language": "en",
                    }
                )
    missing = set(BOOKS) - seen_books
    if missing:
        raise ValueError(f"livros ausentes na entrada: {sorted(missing)}")
    return rows, gaps


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--window", type=int, default=1)
    ap.add_argument("--source-url", default=SOURCE_URL)
    args = ap.parse_args()

    raw = args.input.read_bytes()
    rows, gaps = convert(json.loads(raw), args.window)

    out = CKB_DIR / "corpus" / f"{SOURCE_ID}.jsonl"
    out.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    prov = {
        "source_id": SOURCE_ID,
        "converted_on": date.today().isoformat(),
        "input_url": args.source_url,
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "window": args.window,
        "books": len(BOOKS),
        "passages": len(rows),
        "empty_verses_in_input": gaps,
        "note": "Versículos vazios na fonte foram omitidos; completar manualmente a partir de outra edição.",
    }
    out.with_suffix(".provenance.json").write_text(
        json.dumps(prov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{len(rows)} trechos, {len(gaps)} versículos vazios na fonte → {out}")


if __name__ == "__main__":
    main()
