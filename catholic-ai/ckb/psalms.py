"""Numeração dos Salmos: hebraica (Texto Massorético) <-> Vulgata/LXX.

O canon_ref do CKB usa SEMPRE a numeração da Vulgata. Fontes com numeração hebraica
(WLC, a maioria das traduções modernas) devem passar por aqui.

Níveis de confiança (PsalmRef.confidence):
  exato      capítulos que se dividem/fundem (9-10, 114-115, 116, 147); fronteiras e contagens conferidas
  verificado salmos com divisão interna diferente, resolvidos lendo hebraico e latim (OVERRIDES)
  capitulo   o CAPÍTULO está correto (verificado por contagem e cobertura). O versículo é assumido idêntico:
             passou no teste de deslocamento (scripts/psalms_audit.py) mas NÃO foi lido verso a verso.
"""
from dataclasses import dataclass

END = 999  # "até o último versículo"

# (cap_hebraico, de, até, cap_vulgata, versículo_vulgata_inicial)
SEGMENTS: list[tuple[int, int, int, int, int]] = (
    [(h, 1, END, h, 1) for h in range(1, 9)]
    + [(9, 1, 21, 9, 1), (10, 1, END, 9, 22)]
    + [(h, 1, END, h - 1, 1) for h in range(11, 114)]
    + [(114, 1, END, 113, 1), (115, 1, END, 113, 9)]
    + [(116, 1, 9, 114, 1), (116, 10, END, 115, 1)]
    + [(h, 1, END, h - 1, 1) for h in range(117, 147)]
    + [(147, 1, 11, 146, 1), (147, 12, END, 147, 1)]
    + [(h, 1, END, h, 1) for h in range(148, 151)]
)
STRUCTURAL_HEBREW = {9, 10, 114, 115, 116, 147}


def _complete(n: int, **upd: tuple[int, ...]) -> dict[int, tuple[int, ...]]:
    """Identidade 1..n sobrescrita por upd (chaves 'v12' = versículo 12 da Vulgata)."""
    out = {v: (v,) for v in range(1, n + 1)}
    out.update({int(k[1:]): v for k, v in upd.items()})
    return out


# Vulgata cap -> {versículo vulgata: (versículos hebraicos que o cobrem)}. Capítulo hebraico = cap+1
# nos salmos 10-113 e 117-146; igual à Vulgata em 1-8. Todos verificados lendo o hebraico (OSHB) e o latim.
OVERRIDES: dict[int, dict[int, tuple[int, ...]]] = {
    2: _complete(13, v12=(12,), v13=(12,)),
    4: _complete(10, v6=(6, 7), v7=(7, 8), v8=(8,), v9=(9,), v10=(9,)),
    10: _complete(8, v1=(1,), v2=(1,), v3=(2,), v4=(3,), v5=(4,), v6=(5,), v7=(6,), v8=(7,)),
    12: _complete(6, v1=(1, 2), v2=(3,), v3=(3,)),
    43: _complete(26, v22=(22, 23), v23=(24,), v24=(25,), v25=(26,), v26=(27,)),
    55: _complete(13, v11=(11, 12), v12=(13,), v13=(14,)),
}


@dataclass(frozen=True)
class PsalmRef:
    chapter: int
    verses: tuple[int, ...]
    confidence: str


def _check(ch: int) -> None:
    if not 1 <= ch <= 150:
        raise ValueError(f"salmo inexistente: {ch}")


def _base_h2v(hc: int, hv: int) -> tuple[int, int]:
    for h, lo, hi, vc, v0 in SEGMENTS:
        if h == hc and lo <= hv <= hi:
            return vc, v0 + (hv - lo)
    raise ValueError(f"Sl {hc},{hv} fora do mapa")


def _hebrew_chapter(vc: int) -> int:
    return next(h for h, _, _, v, _ in SEGMENTS if v == vc)


def hebrew_to_vulgate(hc: int, hv: int) -> PsalmRef:
    _check(hc)
    vc, vv = _base_h2v(hc, hv)
    if vc in OVERRIDES:
        verses = tuple(sorted(v for v, hs in OVERRIDES[vc].items() if hv in hs))
        return PsalmRef(vc, verses or (vv,), "verificado")
    return PsalmRef(vc, (vv,), "exato" if hc in STRUCTURAL_HEBREW else "capitulo")


def vulgate_to_hebrew(vc: int, vv: int) -> PsalmRef:
    _check(vc)
    if vc in OVERRIDES:
        return PsalmRef(_hebrew_chapter(vc), OVERRIDES[vc].get(vv, (vv,)), "verificado")
    segs = sorted((s for s in SEGMENTS if s[3] == vc), key=lambda s: s[4], reverse=True)
    for h, lo, _, _, v0 in segs:
        if vv >= v0:
            structural = h in STRUCTURAL_HEBREW
            return PsalmRef(h, (lo + (vv - v0),), "exato" if structural else "capitulo")
    raise ValueError(f"Sl {vc},{vv} fora do mapa")


def hebrew_canon_refs(hc: int, hv: int) -> list[str]:
    """canon_ref(s) (numeração da Vulgata) de um versículo hebraico."""
    r = hebrew_to_vulgate(hc, hv)
    return [f"Ps.{r.chapter}.{v}" for v in r.verses]
