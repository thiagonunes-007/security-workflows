"""Converte Bíblias do scrollmapper/bible_databases (JSON) para o formato do CKB.

Fontes suportadas (PRESETS): douay_rheims (en), vulgata_clementina (la).
Entrada (exemplos):
  curl -sSLO https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/DRC.json
  curl -sSLO https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/VulgClementine.json
Saída: ckb/corpus/<source_id>.jsonl + ckb/corpus/<source_id>.provenance.json

Uso: python -m scripts.convert_scrollmapper_bible douay_rheims DRC.json [--window N]
     python -m scripts.convert_scrollmapper_bible vulgata_clementina VulgClementine.json

- Mantém só os 73 livros do cânon católico (descarta Oração de Manassés, 1-2 Esdras apócrifos,
  Salmo adicional e Laodicenses, presentes nos arquivos mas fora do cânon de Trento).
- Referências em abreviaturas da Bíblia em português (Jo 3,16). Salmos seguem a numeração da
  Vulgata (usada por Douay-Rheims e Vulgata), que difere da hebraica em muitos salmos.
- canon_ref (ex.: John.3.16) alinha o versículo com o mesmo versículo em outras línguas; só é
  gerado com --window 1 (janelas maiores quebram o alinhamento).
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

BASE_URL = "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/"
# source_id -> (idioma, arquivo)
PRESETS = {
    "douay_rheims": ("en", "DRC.json"),
    "vulgata_clementina": ("la", "VulgClementine.json"),
}

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

# nome no arquivo -> id OSIS (chave neutra de idioma usada em canon_ref)
OSIS = {
    "Genesis": "Gen", "Exodus": "Exod", "Leviticus": "Lev", "Numbers": "Num", "Deuteronomy": "Deut",
    "Joshua": "Josh", "Judges": "Judg", "Ruth": "Ruth", "I Samuel": "1Sam", "II Samuel": "2Sam",
    "I Kings": "1Kgs", "II Kings": "2Kgs", "I Chronicles": "1Chr", "II Chronicles": "2Chr",
    "Ezra": "Ezra", "Nehemiah": "Neh", "Tobit": "Tob", "Judith": "Jdt", "Esther": "Esth", "Job": "Job",
    "Psalms": "Ps", "Proverbs": "Prov", "Ecclesiastes": "Eccl", "Song of Solomon": "Song",
    "Wisdom": "Wis", "Sirach": "Sir", "Isaiah": "Isa", "Jeremiah": "Jer", "Lamentations": "Lam",
    "Baruch": "Bar", "Ezekiel": "Ezek", "Daniel": "Dan", "Hosea": "Hos", "Joel": "Joel", "Amos": "Amos",
    "Obadiah": "Obad", "Jonah": "Jonah", "Micah": "Mic", "Nahum": "Nah", "Habakkuk": "Hab",
    "Zephaniah": "Zeph", "Haggai": "Hag", "Zechariah": "Zech", "Malachi": "Mal",
    "I Maccabees": "1Macc", "II Maccabees": "2Macc", "Matthew": "Matt", "Mark": "Mark", "Luke": "Luke",
    "John": "John", "Acts": "Acts", "Romans": "Rom", "I Corinthians": "1Cor", "II Corinthians": "2Cor",
    "Galatians": "Gal", "Ephesians": "Eph", "Philippians": "Phil", "Colossians": "Col",
    "I Thessalonians": "1Thess", "II Thessalonians": "2Thess", "I Timothy": "1Tim", "II Timothy": "2Tim",
    "Titus": "Titus", "Philemon": "Phlm", "Hebrews": "Heb", "James": "Jas", "I Peter": "1Pet",
    "II Peter": "2Pet", "I John": "1John", "II John": "2John", "III John": "3John", "Jude": "Jude",
    "Revelation of John": "Rev",
}
assert set(OSIS) == set(BOOKS)


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def convert(
    data: dict, source_id: str = "douay_rheims", language: str = "en", window: int = 1
) -> tuple[list[dict], list[str]]:
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
                        "source_id": source_id,
                        "canon_ref": f"{OSIS[book['name']]}.{ch['chapter']}.{first}" if window == 1 else "",
                        "ref": f"{abbr} {ch['chapter']},{span}",
                        "text": " ".join(t for _, t in grp),
                        "section": f"{book['name']} {ch['chapter']}"
                        + (" (numeração da Vulgata)" if abbr == "Sl" else ""),
                        "language": language,
                    }
                )
    missing = set(BOOKS) - seen_books
    if missing:
        raise ValueError(f"livros ausentes na entrada: {sorted(missing)}")
    return rows, gaps


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source_id", choices=sorted(PRESETS))
    ap.add_argument("input", type=Path)
    ap.add_argument("--window", type=int, default=1)
    args = ap.parse_args()
    language, filename = PRESETS[args.source_id]
    source_url = BASE_URL + filename

    raw = args.input.read_bytes()
    rows, gaps = convert(json.loads(raw), args.source_id, language, args.window)

    out = CKB_DIR / "corpus" / f"{args.source_id}.jsonl"
    out.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    prov = {
        "source_id": args.source_id,
        "converted_on": date.today().isoformat(),
        "input_url": source_url,
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
