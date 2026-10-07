import json

from ckb.schema import CKB_DIR, load_passages
from scripts.convert_greek import BYZ_FILES, LXX_WORKS, clean, read_byz, read_swete


def test_clean_and_read_byz(tmp_path):
    assert clean("¶Ἐν ἀρχῇ <note>x</note> ἦν  ὁ λόγος") == "Ἐν ἀρχῇ ἦν ὁ λόγος"
    f = tmp_path / "JOH.csv"
    f.write_text('chapter,verse,text\n1,1,"Ἐν ἀρχῇ, ἦν"\n1,2,\n', encoding="utf-8")
    assert read_byz(f) == [(1, 1, "Ἐν ἀρχῇ, ἦν")]  # versículo vazio omitido
    assert len(BYZ_FILES) == 27 and "Dan" in LXX_WORKS and "Eccl" in LXX_WORKS


def test_read_swete_chapters_verses_notes_and_prologue(tmp_path):
    xml = (
        '<body><div type="textpart" subtype="chapter" n="prologue"><div type="textpart" subtype="verse" n="1">'
        "<p>Πρόλογος <lb n='2'/> texto</p></div></div>"
        '<div type="textpart" subtype="chapter" n="1"><head>x</head>'
        '<div type="textpart" subtype="verse" n="1"><p>ἡ δὲ γῆ <note type="marginal">A</note> ἦν ἀόρατος</p></div>'
        '<div type="textpart" subtype="verse" n="2a"><p>ignorado</p></div></div></body>'
    )
    f = tmp_path / "x.xml"
    f.write_text(xml, encoding="utf-8")
    assert read_swete(f) == [(0, 1, "Πρόλογος texto"), (1, 1, "ἡ δὲ γῆ ἦν ἀόρατος")]
    assert read_swete(f, fixed_chapter=13)[1][0] == 13


def corpus(source_id):
    return {p.ref: p for p in load_passages(source_id)}


def test_generated_corpora_have_expected_alignment():
    byz, lxx, de, fr = corpus("byz_nt"), corpus("lxx_swete"), corpus("allioli_de"), corpus("fr_lxx_giguet")
    assert byz["Jo 3,16"].canon_ref == "John.3.16" and byz["Jo 3,16"].align == "identico"
    assert lxx["Gn 1,1"].canon_ref == "Gen.1.1" and lxx["Sl 22,1"].canon_ref == "Ps.22.1"
    assert de["Jo 3,16"].canon_ref == "John.3.16" and "Sohn" in de["Jo 3,16"].text
    assert fr["Gn 1,1"].canon_ref == "Gen.1.1" and fr["Gn 1,1"].text.startswith("Au commencement")
    # livros reprovados na auditoria saem sem alinhamento, mas o texto permanece
    assert all(not p.canon_ref for r, p in lxx.items() if r.startswith("Jó "))
    assert "Jó 1,1" in lxx
    # integridade: nenhum alinhamento aponta para versículo inexistente no latim
    lat = {json.loads(l)["canon_ref"] for l in (CKB_DIR / "corpus" / "vulgata_clementina.jsonl").read_text(encoding="utf-8").splitlines()}
    for c in (byz, lxx, de, fr):
        assert all(p.canon_ref in lat for p in c.values() if p.canon_ref)
