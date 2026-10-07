"""Audita o mapeamento de Salmos contra o hebraico (OSHB) e o latim do CKB.

  curl -sSLO https://raw.githubusercontent.com/openscriptures/morphhb/master/wlc/Ps.xml
  python -m scripts.psalms_audit Ps.xml [--write-counts]

1. Compara contagens de versículos (hebraico mapeado x Vulgata).
2. Teste de deslocamento: salmos fora de OVERRIDES cujo comprimento por versículo correlaciona
   melhor com o latim deslocado em ±1 do que na identidade -> suspeitos de divisão diferente.
   (Heurística de triagem; a confirmação é leitura humana.)
"""
import json
import re
import statistics as st
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

from ckb.psalms import OVERRIDES, hebrew_to_vulgate
from ckb.schema import CKB_DIR

COUNTS = CKB_DIR / "data" / "ps_hebrew_verse_counts.json"


def load_hebrew(xml: str) -> dict[tuple[int, int], int]:
    out = {}
    for m in re.finditer(r'<verse osisID="Ps\.(\d+)\.(\d+)">(.*?)</verse>', xml, re.S):
        words = "".join(re.sub(r"<[^>]+>", "", w) for w in re.findall(r"<w[^>]*>(.*?)</w>", m.group(3), re.S))
        letters = [c for c in unicodedata.normalize("NFD", words) if "א" <= c <= "ת"]
        out[(int(m.group(1)), int(m.group(2)))] = len(letters)
    return out


def load_latin() -> dict[tuple[int, int], int]:
    out = {}
    for line in (CKB_DIR / "corpus" / "vulgata_clementina.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["canon_ref"].startswith("Ps."):
            _, c, v = r["canon_ref"].split(".")
            out[(int(c), int(v))] = len(re.sub(r"\W", "", r["text"]))
    return out


def corr(a, b):
    ma, mb = st.mean(a), st.mean(b)
    d = (sum((i - ma) ** 2 for i in a) * sum((j - mb) ** 2 for j in b)) ** 0.5
    return sum((i - ma) * (j - mb) for i, j in zip(a, b)) / d if d else 0.0


def main(path: str, write_counts: bool) -> None:
    heb, lat = load_hebrew(Path(path).read_text(encoding="utf-8")), load_latin()
    counts = defaultdict(int)
    for (c, v) in heb:
        counts[c] = max(counts[c], v)
    if write_counts:
        COUNTS.write_text(json.dumps({str(c): counts[c] for c in sorted(counts)}, indent=0) + "\n")
    # 1) cobertura: todo versículo latino é coberto por algum hebraico?
    covered = set()
    for (hc, hv) in heb:
        r = hebrew_to_vulgate(hc, hv)
        covered |= {(r.chapter, v) for v in r.verses}
    print(f"hebraico: {len(heb)} versículos | latim: {len(lat)} | latim não coberto: "
          f"{sorted(set(lat) - covered)[:10]} | mapeado sem latim: {sorted(covered - set(lat))}")
    # 2) deslocamento
    by_v = defaultdict(list)
    for (hc, hv), n in sorted(heb.items()):
        r = hebrew_to_vulgate(hc, hv)
        if r.chapter not in OVERRIDES and len(r.verses) == 1:
            by_v[r.chapter].append((r.verses[0], n))
    sus = []
    for vc, rows in by_v.items():
        if len(rows) < 6:
            continue
        def c_at(s):
            pairs = [(n, lat[(vc, v + s)]) for v, n in rows if (vc, v + s) in lat]
            return corr(*zip(*pairs)) if len(pairs) >= 5 else -1
        base = c_at(0)
        best = max((c_at(-1), -1), (c_at(1), 1))
        if best[0] > base + 0.15:
            sus.append((vc, round(base, 2), best[1], round(best[0], 2)))
    print("suspeitos (cap. Vulgata, corr. identidade, deslocamento, corr. deslocada):")
    for s in sorted(sus):
        print(" ", s)


if __name__ == "__main__":
    main(sys.argv[1], "--write-counts" in sys.argv)
