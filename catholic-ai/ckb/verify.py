"""Verificação independente de alinhamento grego <-> latim por nomes próprios.

O alinhador usa só comprimento; esta checagem usa um sinal diferente: nomes próprios transliterados.
O esqueleto consonantal de "Ἰσραήλ" e de "Israël" é o mesmo ("srl"). Para cada par alinhado com nomes no
latim, vê se ao menos um bate com alguma palavra grega.
"""
import re
import unicodedata

_GR = {"α": "", "ε": "", "η": "", "ι": "", "ο": "", "υ": "", "ω": "", "β": "b", "γ": "g", "δ": "d", "ζ": "z",
       "θ": "t", "κ": "k", "λ": "l", "μ": "m", "ν": "n", "ξ": "ks", "π": "p", "ρ": "r", "σ": "s", "ς": "s",
       "τ": "t", "φ": "f", "χ": "k", "ψ": "ps"}


def greek_key(word: str) -> str:
    w = "".join(c for c in unicodedata.normalize("NFD", word.lower()) if unicodedata.category(c) != "Mn")
    w = w.replace("γγ", "ng").replace("γκ", "nk").replace("γχ", "nk")
    return re.sub(r"(.)\1+", r"\1", "".join(_GR.get(c, "") for c in w))


def latin_key(word: str) -> str:
    w = unicodedata.normalize("NFD", word.lower())
    w = "".join(c for c in w if unicodedata.category(c) != "Mn").replace("æ", "ae").replace("œ", "oe")
    w = w.replace("ph", "f").replace("th", "t").replace("ch", "k").replace("sch", "s")
    w = re.sub(r"[aeiouyhvj]", "", w).replace("c", "k").replace("q", "k")
    return re.sub(r"(.)\1+", r"\1", w)


# chaves (3 consoantes) de palavras teológicas comuns que o latim capitaliza mas o grego não translitera
STOP = {"dmn", "spr", "snk", "ngl", "skr", "mgs", "slb", "sbb", "kls", "frs", "vrb", "ngl"}


def names(latin: str) -> set[str]:
    """Palavras capitalizadas fora do início de frase (nomes próprios), por chave de 3 consoantes."""
    out = set()
    for m in re.finditer(r"[\w’']+", latin):
        t = m.group()
        prev = latin[: m.start()].rstrip()[-1:]
        if not prev or prev in ".:;!?" or not t[0].isupper():
            continue
        k = latin_key(t)
        if len(k) >= 3 and k[:3] not in STOP:
            out.add(k[:3])
    return out


def agrees(text: str, latin: str, script: str = "grc") -> bool | None:
    """True/False se há nomes no latim; None se não há (sem sinal). script: 'grc' ou 'latin' (fr/es/it/pt/de)."""
    ns = names(latin)
    if not ns:
        return None
    key = greek_key if script == "grc" else latin_key
    gk = {key(w)[:3] for w in re.findall(r"\w+", text) if len(key(w)) >= 3}
    return bool(ns & gk)


def filter_alignments(rows: list[dict], latin_text: dict[str, str], min_rate: float = 0.65, min_n: int = 8,
                      script: str = "grc"):
    """Remove (canon_ref vazio) os alinhamentos que a checagem por nomes não sustenta. Retorna (rows, relatório).

    Regra, por livro e rótulo (``align``):
      - rótulo com >= min_n pares com sinal: mantido só se a concordância >= min_rate;
      - "identico": também mantido com poucos pares, desde que o livro não seja reprovado (livro reprovado =
        "identico" com >= min_n pares abaixo de min_rate, ou, com poucos pares, concordância geral < 0.55);
      - demais rótulos com poucos pares: descartados (sem como verificar).
    """
    from collections import defaultdict

    stat = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for r in rows:
        if not r["canon_ref"]:
            continue
        lt = latin_text.get(r["canon_ref"], "") + (" " + latin_text.get(r["canon_ref_2"], "") if r["canon_ref_2"] else "")
        a = agrees(r["text"], lt, script)
        if a is not None:
            s = stat[r["canon_ref"].split(".")[0]][r["align"]]
            s[0] += a
            s[1] += 1
    report, keep = {}, {}
    for book, labels in stat.items():
        ident = labels.get("identico", [0, 0])
        tot_ok, tot_n = sum(v[0] for v in labels.values()), sum(v[1] for v in labels.values())
        if ident[1] >= min_n:
            book_ok = ident[0] / ident[1] >= min_rate
        else:
            book_ok = tot_n < 5 or tot_ok / tot_n >= 0.55
        keep[book] = {"book_ok": book_ok}
        for lab, (ok, n) in labels.items():
            if lab == "identico":
                k = book_ok
            else:
                k = n >= min_n and ok / n >= min_rate
            keep[book][lab] = k
        report[book] = {lab or "-": {"ok": ok, "n": n, "rate": round(ok / n, 2), "kept": keep[book][lab]}
                        for lab, (ok, n) in labels.items()}
    out, dropped = [], 0
    for r in rows:
        b = r["canon_ref"].split(".")[0] if r["canon_ref"] else ""
        if r["canon_ref"]:
            verdict = keep.get(b)
            # livros/rótulos sem sinal algum: mantém só "identico"
            ok = (verdict[r["align"]] if verdict and r["align"] in verdict else (r["align"] == "identico" and (verdict or {"book_ok": True})["book_ok"]))
            if not ok:
                r = {**r, "canon_ref": "", "canon_ref_2": "", "align": ""}
                dropped += 1
        out.append(r)
    return out, {"dropped": dropped, "by_book_label": report}
