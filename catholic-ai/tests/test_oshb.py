import json

from ckb.books_map import daniel_to_vulgate, esther_to_vulgate
from ckb.schema import CKB_DIR, load_passages
from scripts.convert_oshb_hebrew import OSHB_BOOKS, letters, verse_text


def test_verse_text_handles_notes_maqqef_and_wrappers():
    body = (
        '<w lemma="a">בְּ/רֵאשִׁ֖ית</w><w>בָּרָ֣א</w><seg type="x-maqqef">־</seg><w>אֱלֹהִ֑ים</w>'
        '<note type="variant"><catchWord>x</catchWord><rdg type="x-qere"><w>QERE</w></rdg></note>'
        '<seg type="x-large"><w>הָ/אָֽרֶץ</w></seg><seg type="x-paseq">׀</seg><w>סוף</w>'
        '<seg type="x-pe">פ</seg><seg type="x-sof-pasuq">׃</seg>'
    )
    t = verse_text(body)
    assert "QERE" not in t and "/" not in t
    assert t.startswith("בְּרֵאשִׁ֖ית בָּרָ֣א־אֱלֹהִ֑ים הָאָֽרֶץ")  # maqaf cola as palavras
    assert t.endswith("׃") and " ׀ " in t
    assert letters("בְּרֵאשִׁית") == 6


def test_structural_maps():
    assert esther_to_vulgate(10, 3) == (10, 3)
    assert [daniel_to_vulgate(3, v) for v in (23, 24, 33)] == [(3, 23), (3, 91), (3, 100)]
    assert [daniel_to_vulgate(6, v) for v in (1, 2, 29)] == [(5, 31), (6, 1), (6, 28)]
    assert daniel_to_vulgate(12, 13) == (12, 13)


def test_structural_boundaries_match_latin_text():
    lat = {}
    for line in (CKB_DIR / "corpus" / "vulgata_clementina.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        lat[r["canon_ref"]] = r["text"]
    assert "obstupuit" in lat["Dan.3.91"]  # Heb Dn 3,24 (Nabucodonosor se espanta)
    assert "Darius Medus" in lat["Dan.5.31"]  # Heb Dn 6,1
    assert "Placuit Dario" in lat["Dan.6.1"]  # Heb Dn 6,2
    assert "Mardochæus" in lat["Esth.10.3"]  # fim do hebraico; 10,4 em diante = acréscimos


def test_generated_corpus_is_valid_and_aligned():
    ps = load_passages("wlc_hebrew")  # valida esquema e refs únicas
    assert len(ps) == 23213 and all(p.language == "hbo" or p.language == "" for p in ps)
    by = {p.ref: p for p in ps}
    expect = {
        "Gn 1,1": "Gen.1.1", "Gn 32,1": "Gen.31.55", "Jl 3,1": "Joel.2.28", "Ml 3,19": "Mal.4.1",
        "Nm 17,1": "Num.16.36", "Dt 13,1": "Deut.12.32", "Is 8,23": "Isa.9.1", "Jó 40,25": "Job.40.20",
        "Ne 10,1": "Neh.9.38", "Dn 3,24": "Dan.3.91", "Sl 23,1": "Ps.22.1", "Sl 116,10": "Ps.115.1",
    }
    for ref, canon in expect.items():
        assert by[ref].canon_ref == canon, (ref, by[ref].canon_ref)
    assert (by["Sl 13,3"].canon_ref, by["Sl 13,3"].canon_ref_2) == ("Ps.12.2", "Ps.12.3")
    assert by["Nm 25,19"].canon_ref == by["Nm 26,1"].canon_ref == "Num.26.1"  # 2 hebraicos = 1 latino
    books = {p.canon_ref.split(".")[0] for p in ps if p.canon_ref}
    assert books == set(OSHB_BOOKS)
