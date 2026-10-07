import json

import pytest

from ckb.psalms import OVERRIDES, hebrew_canon_refs, hebrew_to_vulgate, vulgate_to_hebrew
from ckb.schema import CKB_DIR

KNOWN_LATIN_GAPS = {(15, 11), (42, 6), (125, 7), (135, 27)}  # versículos vazios na fonte


def latin():
    out = {}
    for line in (CKB_DIR / "corpus" / "vulgata_clementina.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["canon_ref"].startswith("Ps."):
            _, c, v = r["canon_ref"].split(".")
            out[(int(c), int(v))] = r["text"]
    return out


def hebrew_counts():
    raw = json.loads((CKB_DIR / "data" / "ps_hebrew_verse_counts.json").read_text())
    return {int(k): v for k, v in raw.items()}


@pytest.mark.parametrize(
    "heb, vul",
    [
        ((1, 1), (1, (1,))),
        ((23, 1), (22, (1,))),  # "O Senhor é meu pastor": Sl 23 hebraico = Sl 22 Vulgata
        ((51, 3), (50, (3,))),  # Miserere
        ((10, 1), (9, (22,))),  # fusão 9+10
        ((115, 1), (113, (9,))),  # "Non nobis"
        ((116, 10), (115, (1,))),  # divisão do 116
        ((147, 12), (147, (1,))),  # divisão do 147
        ((130, 1), (129, (1,))),  # De profundis
        ((150, 6), (150, (6,))),
        ((44, 24), (43, (23,))),  # override: Sl 44 hebraico deslocado
        ((13, 3), (12, (2, 3))),  # override: 13,3 cobre dois versículos latinos
    ],
)
def test_hebrew_to_vulgate_known_points(heb, vul):
    r = hebrew_to_vulgate(*heb)
    assert (r.chapter, r.verses) == vul


def test_every_hebrew_verse_maps_and_every_latin_verse_is_covered():
    lat = latin()
    covered = set()
    for hc, n in hebrew_counts().items():
        for hv in range(1, n + 1):
            r = hebrew_to_vulgate(hc, hv)
            covered |= {(r.chapter, v) for v in r.verses}
    assert set(lat) - covered == set()  # nenhum versículo latino órfão
    assert covered - set(lat) <= KNOWN_LATIN_GAPS  # só lacunas conhecidas da fonte


def test_round_trip_vulgate_to_hebrew_and_back():
    for (vc, vv) in latin():
        r = vulgate_to_hebrew(vc, vv)
        back = {(x.chapter, v) for h in r.verses for x in [hebrew_to_vulgate(r.chapter, h)] for v in x.verses}
        assert (vc, vv) in back, (vc, vv, r, back)


def test_structural_boundaries_match_latin_text():
    lat = latin()
    assert "Ut quid, Domine, recessisti" in lat[(9, 22)][:40]  # Heb 10,1
    assert "Non nobis" in lat[(113, 9)][:40]  # Heb 115,1
    assert "Credidi" in lat[(115, 1)][:40]  # Heb 116,10
    assert "Lauda" in lat[(147, 1)][:40]  # Heb 147,12
    assert "In exitu" in lat[(114, 1)][:40]  # Heb 114,1


def test_confidence_levels_and_bad_input():
    assert hebrew_to_vulgate(10, 5).confidence == "exato"
    assert hebrew_to_vulgate(44, 5).confidence == "verificado"
    assert hebrew_to_vulgate(80, 5).confidence == "capitulo"
    assert hebrew_canon_refs(13, 3) == ["Ps.12.2", "Ps.12.3"]
    assert set(OVERRIDES) == {2, 4, 10, 12, 43, 55}
    with pytest.raises(ValueError):
        hebrew_to_vulgate(151, 1)
