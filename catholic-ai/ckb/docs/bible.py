"""Bíblias em texto corrido (OCR ou digital) -> versículos (livro, capítulo, versículo).

Pensado para traduções da Vulgata em pt/it/es (Figueiredo, Martini, Torres Amat, Scío...). Passos:
  1. split_books: acha os títulos de livro (fuzzy, tolera grafia antiga: "Mathêus", "Esther", "Ezechiel").
  2. parse_book: capítulos ("CAPÍTULO III", "Cap. 3") e versículos numerados no meio do texto.
     A numeração é guiada pela SEQUÊNCIA (1, 2, 3...): um "7" só vale como versículo se o anterior era 6,
     o que elimina quase todo falso positivo de OCR (datas, notas, citações).
  3. qa_counts: compara versículos por capítulo com a Vulgata do CKB — Bíblias da Vulgata devem bater quase 100%.
"""
import difflib
import re
import unicodedata

ORD = {"1": 1, "i": 1, "primeiro": 1, "primeira": 1, "prima": 1, "primo": 1, "primera": 1, "primero": 1,
       "2": 2, "ii": 2, "segundo": 2, "segunda": 2, "seconda": 2, "secondo": 2,
       "3": 3, "iii": 3, "terceiro": 3, "terceira": 3, "terza": 3, "terzo": 3, "tercera": 3, "tercero": 3,
       "4": 4, "iv": 4, "quarto": 4, "quarta": 4, "cuarto": 4, "cuarta": 4, "quarto": 4}
# palavra-chave (sem acento, minúscula, th->t, ph->f) -> OSIS ou (prefixo_osis_por_ordinal)
KEYS = {
    "genesis": "Gen", "exodo": "Exod", "esodo": "Exod", "levitico": "Lev", "numeros": "Num", "numeri": "Num",
    "deuteronomio": "Deut", "josue": "Josh", "giosue": "Josh", "juizes": "Judg", "giudici": "Judg", "jueces": "Judg",
    "rute": "Ruth", "rut": "Ruth", "tobias": "Tob", "tobia": "Tob", "tobit": "Tob", "judite": "Jdt", "juditi": "Jdt",
    "giuditta": "Jdt", "ester": "Esth", "estere": "Esth", "job": "Job", "giobbe": "Job", "salmos": "Ps", "salmi": "Ps",
    "proverbios": "Prov", "proverbi": "Prov", "eclesiastes": "Eccl", "ecclesiaste": "Eccl", "coelet": "Eccl",
    "qohelet": "Eccl", "cantares": "Song", "canticos": "Song", "cantici": "Song", "cantar": "Song",
    "sabedoria": "Wis", "sapienza": "Wis", "sabiduria": "Wis", "eclesiastico": "Sir", "sirach": "Sir",
    "siracide": "Sir", "isaias": "Isa", "isaia": "Isa", "jeremias": "Jer", "geremia": "Jer",
    "lamentacoes": "Lam", "lamentazioni": "Lam", "lamentaciones": "Lam", "baruch": "Bar", "baruc": "Bar",
    "ezequiel": "Ezek", "ezechiel": "Ezek", "ezechiele": "Ezek", "daniel": "Dan", "daniele": "Dan", "oseas": "Hos",
    "osea": "Hos", "joel": "Joel", "gioele": "Joel", "amos": "Amos", "abdias": "Obad", "abdia": "Obad",
    "jonas": "Jonah", "giona": "Jonah", "miqueias": "Mic", "michea": "Mic", "miqueas": "Mic", "nahum": "Nah",
    "naum": "Nah", "habacuc": "Hab", "abacuc": "Hab", "sofonias": "Zeph", "sofonia": "Zeph", "ageu": "Hag",
    "aggeu": "Hag", "aggeo": "Hag", "zacarias": "Zech", "zaccaria": "Zech", "malaquias": "Mal", "malachia": "Mal",
    "mateus": "Matt", "matteo": "Matt", "mateo": "Matt", "marcos": "Mark", "marco": "Mark", "lucas": "Luke",
    "luca": "Luke", "atos": "Acts", "actos": "Acts", "atti": "Acts", "romanos": "Rom", "romani": "Rom",
    "galatas": "Gal", "galati": "Gal", "efesios": "Eph", "efesini": "Eph", "filipenses": "Phil", "filippesi": "Phil",
    "colossenses": "Col", "colossesi": "Col", "colosenses": "Col", "tito": "Titus", "filemon": "Phlm",
    "filemone": "Phlm", "hebreus": "Heb", "ebrei": "Heb", "hebreos": "Heb", "tiago": "Jas", "giacomo": "Jas",
    "santiago": "Jas", "judas": "Jude", "giuda": "Jude", "apocalipse": "Rev", "apocalisse": "Rev",
    "apocalipsis": "Rev", "esdras": "ESDRAS", "esdra": "ESDRAS", "neemias": "Neh", "nehemias": "Neh",
    "neemia": "Neh",
}
# com ordinal: palavra-chave -> {ordinal: OSIS}; "reis"/"reyes"/"re" dependem do esquema (vulgata: 1-4 Reis)
ORDINAL_KEYS = {
    "samuel": {1: "1Sam", 2: "2Sam"}, "paralipomenos": {1: "1Chr", 2: "2Chr"}, "paralipomeni": {1: "1Chr", 2: "2Chr"},
    "cronicas": {1: "1Chr", 2: "2Chr"}, "cronache": {1: "1Chr", 2: "2Chr"}, "macabeus": {1: "1Macc", 2: "2Macc"},
    "maccabei": {1: "1Macc", 2: "2Macc"}, "macabeos": {1: "1Macc", 2: "2Macc"},
    "corintios": {1: "1Cor", 2: "2Cor"}, "corinzi": {1: "1Cor", 2: "2Cor"},
    "tessalonicenses": {1: "1Thess", 2: "2Thess"}, "tessalonicesi": {1: "1Thess", 2: "2Thess"},
    "tesalonicenses": {1: "1Thess", 2: "2Thess"}, "timoteo": {1: "1Tim", 2: "2Tim"},
    "pedro": {1: "1Pet", 2: "2Pet"}, "pietro": {1: "1Pet", 2: "2Pet"},
    "joao": {0: "John", 1: "1John", 2: "2John", 3: "3John"}, "giovanni": {0: "John", 1: "1John", 2: "2John", 3: "3John"},
    "juan": {0: "John", 1: "1John", 2: "2John", 3: "3John"},
}
KINGS = {"reis": None, "reyes": None, "re": None}
KINGS_VULGATE = {1: "1Sam", 2: "2Sam", 3: "1Kgs", 4: "2Kgs"}
KINGS_MODERN = {1: "1Kgs", 2: "2Kgs"}
EZRA_NEH = {1: "Ezra", 2: "Neh"}
IGNORE = set("""livro libro o de do dos das da dei di il el la los las evangelho vangelo evangelio segundo secondo san sao
s santo santa epistola epistole carta lettera aos ao agli ai a los primeira primeiro segunda terceira quarta
prima seconda terza primera profecia profeta profezia do dos e actos apostolos apostoli apostolicas""".split())
_CHAP = re.compile(r"^\s*(?:cap(?:[ií]tulo|itolo|\.)?|capitulo)\s+([ivxlcdm]+|\d+)\b\.?", re.I)
_ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.replace("th", "t").replace("ph", "f").replace("ch", "c") if False else s.replace("th", "t").replace("ph", "f")


def roman(s: str) -> int:
    t = 0
    for a, b in zip(s.lower(), s.lower()[1:] + " "):
        t += -_ROMAN[a] if _ROMAN.get(b, 0) > _ROMAN[a] else _ROMAN[a]
    return t


def detect_book(line: str, scheme: str = "vulgata") -> str | None:
    """OSIS do livro se `line` parecer um título de livro; senão None."""
    plain = re.sub(r"\b[A-Za-z]{1,3}\.", "", line)  # abreviaturas ("S. João", "Sto.")
    if len(line) > 70 or re.search(r"[.;]\s*\S", plain.strip().rstrip(".")) or re.search(r"\d{2,}", line):
        return None
    toks = [t for t in re.split(r"[^a-z0-9]+", fold(line)) if t]
    if not toks or len(toks) > 9:
        return None
    ordinal = next((ORD[t] for t in toks if t in ORD), None)
    if {"evangelho", "vangelo", "evangelio"} & set(toks):
        ordinal = None  # "Evangelho SEGUNDO S. João": "segundo" = "conforme", não é ordinal
    words = [t for t in toks if t not in IGNORE and t not in ORD and not t.isdigit()]
    allkeys = list(KEYS) + list(ORDINAL_KEYS) + list(KINGS)
    for w in words:
        k = w if w in allkeys else (difflib.get_close_matches(w, allkeys, 1, 0.84) or [None])[0]
        if k is None:
            continue
        if k in KEYS:
            osis = KEYS[k]
            return EZRA_NEH.get(ordinal or 1) if osis == "ESDRAS" else osis
        if k in ORDINAL_KEYS:
            table = ORDINAL_KEYS[k]
            return table.get(ordinal or (0 if 0 in table else 1))
        if k in KINGS:
            return (KINGS_VULGATE if scheme == "vulgata" else KINGS_MODERN).get(ordinal or 1)
    return None


def split_books(paras_or_lines: list[str], scheme: str = "vulgata") -> dict[str, list[str]]:
    """Divide em livros pelos títulos; um título só vale se seguido de capítulo (ou verso 1) nas próximas linhas."""
    idx = []
    for i, l in enumerate(paras_or_lines):
        b = detect_book(l, scheme)
        if b and any(_CHAP.match(x) or re.match(r"^\s*1[.\s]", x) for x in paras_or_lines[i + 1:i + 5]):
            idx.append((i, b))
    out: dict[str, list[str]] = {}
    for (i, b), nxt in zip(idx, idx[1:] + [(len(paras_or_lines), None)]):
        if b not in out:  # primeira ocorrência (índices e sumários repetem títulos)
            out[b] = paras_or_lines[i + 1:nxt[0]]
    return out


def parse_book(lines: list[str]) -> tuple[list[tuple[int, int, str]], list[str]]:
    """Linhas de um livro -> [(cap, vers, texto)] e lista de problemas."""
    verses, issues = [], []
    chapters: list[tuple[int, list[str]]] = []
    for l in lines:
        m = _CHAP.match(l)
        if m:
            raw = m.group(1)
            n = int(raw) if raw.isdigit() else roman(raw)
            chapters.append((n, [l[m.end():].strip()]))
        elif chapters:
            chapters[-1][1].append(l)
        elif l.strip():
            issues.append(f"texto antes do 1º capítulo: {l[:40]!r}")
    if not chapters:  # livro de capítulo único (Abdias, Filemon, 2-3 João, Judas): verso 1 em diante
        chapters = [(1, lines)]
    for n, parts in chapters:
        body = " ".join(" ".join(parts).split())
        pos, exp, found = 0, 1, []
        while True:
            m = re.compile(rf"(?<![\w.,]){exp}(?=[\s.)\]–-]+[^\W\d_])").search(body, pos)
            skip = 0
            while not m and skip < 2:  # tolera 1-2 versículos ilegíveis
                skip += 1
                m = re.compile(rf"(?<![\w.,]){exp + skip}(?=[\s.)\]–-]+[^\W\d_])").search(body, pos)
            if not m:
                break
            if skip:
                issues.append(f"cap {n}: versículo(s) {exp}..{exp + skip - 1} não encontrado(s)")
            found.append((exp + skip, m.start(), m.end()))
            pos, exp = m.end(), exp + skip + 1
        for k, (v, _, e) in enumerate(found):
            end = found[k + 1][1] if k + 1 < len(found) else len(body)
            text = body[e:end].strip(" .\t\n")
            verses.append((n, v, text if text else ""))
        if not found:
            issues.append(f"cap {n}: nenhum versículo numerado")
    return [v for v in verses if v[2]], issues


def qa_counts(verses: list[tuple[int, int, str]], latin_counts: dict[int, int]) -> dict:
    """Compara com a Vulgata do CKB: capítulos e versículos esperados x encontrados."""
    got: dict[int, set[int]] = {}
    for c, v, _ in verses:
        got.setdefault(c, set()).add(v)
    chapters = sorted(set(got) | set(latin_counts))
    missing = {c: sorted(set(range(1, latin_counts.get(c, 0) + 1)) - got.get(c, set())) for c in chapters}
    missing = {c: m for c, m in missing.items() if m}
    extra = {c: sorted(v for v in got[c] if v > latin_counts.get(c, 0)) for c in got}
    extra = {c: e for c, e in extra.items() if e}
    expected = sum(latin_counts.values())
    found = expected - sum(len(m) for m in missing.values())
    return {"chapters_parsed": len(got), "chapters_expected": len(latin_counts),
            "verses_expected": expected, "verses_found_of_expected": found,
            "coverage": round(found / max(1, expected), 3),
            "missing": {c: m[:12] for c, m in list(missing.items())[:15]},
            "beyond_vulgate": {c: e[:6] for c, e in list(extra.items())[:10]}}
