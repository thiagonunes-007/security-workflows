"""Limpeza de texto extraído/OCR: ligaduras, hifenização, cabeçalhos/rodapés repetidos, números de página."""
import re
import unicodedata
from collections import Counter

LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st", "ſ": "s",
             "­": "", "​": "", "﻿": ""}
_PAGE_NUM = re.compile(r"^\s*[-–—\[(]?\s*(\d{1,4}|[ivxlcdmIVXLCDM]{1,7})\s*[-–—\])]?\s*$")


def normalize(text: str) -> str:
    for a, b in LIGATURES.items():
        text = text.replace(a, b)
    return unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))


def _key(line: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", line.strip().lower()))


def strip_running_heads(pages: list[str], min_pages: int = 4, ratio: float = 0.4) -> list[str]:
    """Remove linhas (1as/últimas de cada página) que se repetem em >= `ratio` das páginas, e nº de página."""
    split = [[l for l in p.split("\n")] for p in pages]
    if len(pages) >= min_pages:
        cnt = Counter()
        for lines in split:
            nz = [l for l in lines if l.strip()]
            for l in set(nz[:2] + nz[-2:]):
                if len(l.strip()) > 2:
                    cnt[_key(l)] += 1
        common = {k for k, n in cnt.items() if n >= ratio * len(pages)}
    else:
        common = set()
    out = []
    for lines in split:
        keep = []
        nz_idx = [i for i, l in enumerate(lines) if l.strip()]
        edge = set(nz_idx[:2] + nz_idx[-2:])
        for i, l in enumerate(lines):
            if i in edge and (_key(l) in common or _PAGE_NUM.match(l)):
                continue
            keep.append(l)
        out.append("\n".join(keep))
    return out


def dehyphenate(text: str) -> str:
    return re.sub(r"(\w)[-¬]\n\s*([a-zà-ÿ])", r"\1\2", text)


_START = re.compile(r"^\(?\d{1,4}[.)]\s+[A-ZÀ-ÝÁÉÍÓÚ«“\"]")
_END = re.compile(r"[.!?:;»”)\"]$")


def paragraphs(text: str) -> list[str]:
    """Quebra por linha em branco; une quebras de linha dentro do parágrafo. Também abre parágrafo novo quando uma
    linha começa com número crescente ("2. Para...") depois de frase terminada, ou quando um título em CAIXA ALTA
    aparece — o pdftotext costuma entregar parágrafos numerados sem linha em branco entre eles."""
    out = []
    for block in re.split(r"\n\s*\n", dehyphenate(text)):
        cur: list[str] = []
        for line in block.split("\n"):
            l = " ".join(line.split())
            if not l:
                continue
            prev = cur[-1] if cur else ""
            new = bool(cur) and (
                (_START.match(l) and _END.search(prev))
                or (l.isupper() and len(l) < 80 and (prev.isupper() or _END.search(prev)))
                or (prev.isupper() and len(prev) < 80 and not l.isupper()))
            if new:
                out.append(" ".join(cur))
                cur = []
            cur.append(l)
        if cur:
            out.append(" ".join(cur))
    return out


def clean_document(pages: list[str]) -> list[str]:
    """páginas brutas -> parágrafos limpos (todas as páginas, em ordem)."""
    pages = strip_running_heads([normalize(p) for p in pages])
    buf = ""
    for p in pages:
        p = p.strip("\n")
        # parágrafo que atravessa a quebra de página: continua se não terminou frase e a próxima começa em minúscula
        cont = buf and not re.search(r"[.!?:;»”\")]\s*$", buf) and re.match(r"\s*[a-zà-ÿ]", p)
        buf += ("\n" if cont else "\n\n") + p
    return paragraphs(buf)
