"""Alinhamento de versículos entre duas versões por comprimento (Gale-Church simplificado).

Serve para ligar textos cuja numeração difere (ex.: hebraico x Vulgata) quando não há tabela de
concordância. Programação dinâmica sobre "beads": 1:1, 1:2, 2:1, 2:2, 1:3, 3:1 e lacunas (1:0, 0:1).
Heurística: validada contra o mapeamento de Salmos (99,6% de concordância), mas NÃO substitui revisão.
"""
import math

# (versículos A, versículos B, penalidade)
BEADS = [(1, 1, 0.0), (1, 2, 3.5), (2, 1, 3.5), (2, 2, 5.0), (1, 3, 7.0), (3, 1, 7.0), (1, 0, 9.0), (0, 1, 9.0)]


def align(a_lens: list[int], b_lens: list[int], band: int = 150, sigma: float = 0.45):
    """Retorna beads [(índices_A, índices_B)] em ordem. `band` deve superar |len(A)-len(B)|."""
    n, m = len(a_lens), len(b_lens)
    band = max(band, abs(n - m) + 40)
    ratio = sum(b_lens) / max(1, sum(a_lens))
    pa, pb = [0], [0]
    for x in a_lens:
        pa.append(pa[-1] + x)
    for x in b_lens:
        pb.append(pb[-1] + x)

    def match_cost(i0, i1, j0, j1):
        a = (pa[i1] - pa[i0]) * ratio
        b = pb[j1] - pb[j0]
        return math.log((b + 8) / (a + 8)) ** 2 / (2 * sigma**2)

    cost = {(0, 0): 0.0}
    back = {}
    for i in range(n + 1):
        for j in range(max(0, i - band), min(m, i + band) + 1):
            c0 = cost.get((i, j))
            if c0 is None:
                continue
            for di, dj, pen in BEADS:
                ni, nj = i + di, j + dj
                if ni > n or nj > m or abs(ni - nj) > band:
                    continue
                c = c0 + pen + match_cost(i, ni, j, nj)
                if c < cost.get((ni, nj), math.inf):
                    cost[(ni, nj)] = c
                    back[(ni, nj)] = (i, j)
    path, cur = [], (n, m)
    while cur != (0, 0):
        p = back[cur]
        path.append((tuple(range(p[0], cur[0])), tuple(range(p[1], cur[1]))))
        cur = p
    return path[::-1]


def classify_book(native, a_lens, latin, max_odd: float = 0.4):
    """Alinha um livro a ``latin`` e rotula cada versículo.

    native: [(cap, vers)] do texto A; a_lens: comprimentos; latin: [((cap, vers), comprimento)].
    Retorna (res, stats). res[i] = {"refs": [(cap, vers), ...], "label": ...}.
    Rótulos: identico | deslocado | incerto | "" (sem par). TRAVA DE QUALIDADE: se mais de ``max_odd`` dos
    versículos estiver em regiões não 1:1 (sinal de acréscimos/reordenação que o método não resolve),
    o livro inteiro fica SEM alinhamento em vez de com pares errados.
    """
    beads = align(a_lens, [n for _, n in latin])
    res = [{"refs": [], "label": ""} for _ in native]
    odd = set()
    for hi, li in beads:
        if len(hi) == 1 and len(li) == 1:
            continue
        for i in range(max(0, hi[0] - 2 if hi else 0), min(len(native), (hi[-1] + 3) if hi else 0)):
            odd.add(i)
    frac = len(odd) / max(1, len(native))
    stats = {"verses": len(native), "odd_fraction": round(frac, 3), "aligned": frac <= max_odd}
    if frac > max_odd:
        return res, stats
    for hi, li in beads:
        for i in hi:
            if li:
                res[i]["refs"] = [latin[j][0] for j in li][:2]
                same = len(hi) == len(li) == 1 and latin[li[0]][0] == native[i]
                res[i]["label"] = "incerto" if (i in odd or len(hi) != len(li)) else (
                    "identico" if same else "deslocado")
    return res, stats
