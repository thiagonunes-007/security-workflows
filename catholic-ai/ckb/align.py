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
