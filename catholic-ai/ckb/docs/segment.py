"""Segmentação em trechos citáveis: documentos numerados (magistério), prosa livre."""
import re

_NUM = re.compile(r"^\(?(\d{1,4})[.)]?\s+(?=\S)")
_SENT = re.compile(r"(?<=[.!?…])\s+(?=[A-ZÀ-ÝÁÉÍÓÚ«“\"'])")


def is_heading(p: str) -> bool:
    w = p.split()
    return 0 < len(w) <= 12 and len(p) < 100 and not p.endswith((".", ";", ",")) and (
        p.isupper() or sum(x[0].isupper() for x in w if x[0].isalpha()) >= max(1, len(w) * 0.6))


def numbered(paras: list[str], sigla: str, max_gap: int = 3) -> list[dict]:
    """Um trecho por parágrafo numerado (CIC, encíclicas, Vaticano II). A numeração tem de ser crescente:
    isso evita confundir datas, listas e números de nota com o início de um parágrafo."""
    out, cur, last, section = [], None, 0, ""
    for p in paras:
        m = _NUM.match(p)
        n = int(m.group(1)) if m else 0
        if m and last < n <= (last + max_gap if last else 50):
            cur = {"ref": f"{sigla} {int(m.group(1))}", "text": p[m.end():].strip(), "section": section}
            out.append(cur)
            last = int(m.group(1))
        elif is_heading(p):
            section = p.title() if p.isupper() else p
            cur = None
        elif cur is not None:
            cur["text"] += " " + p  # continuação (subitens, citações)
    return [o for o in out if len(o["text"]) >= 20]


def prose(paras: list[str], sigla: str, target_words: int = 220, max_words: int = 380) -> list[dict]:
    """Janelas de parágrafos inteiros (~target_words); parágrafo gigante é partido por frases."""
    out, buf, words, section = [], [], 0, ""

    def flush():
        nonlocal buf, words
        if buf:
            out.append({"ref": f"{sigla} #{len(out) + 1}", "text": " ".join(buf), "section": section})
            buf, words = [], 0

    for p in paras:
        if is_heading(p):
            flush()
            section = p.title() if p.isupper() else p
            continue
        pieces = [p]
        if len(p.split()) > max_words:
            pieces, acc = [], ""
            for s in _SENT.split(p):
                if acc and len((acc + " " + s).split()) > target_words:
                    pieces.append(acc)
                    acc = s
                else:
                    acc = (acc + " " + s).strip()
            pieces.append(acc)
        for piece in pieces:
            n = len(piece.split())
            if words and words + n > max_words:
                flush()
            buf.append(piece)
            words += n
            if words >= target_words:
                flush()
    flush()
    return [o for o in out if len(o["text"]) >= 20]
