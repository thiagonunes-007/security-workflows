import json
import shutil
from pathlib import Path

import pytest
import yaml

from ckb.docs.bible import detect_book, parse_book, split_books
from ckb.docs.clean import clean_document, paragraphs, strip_running_heads
from ckb.docs.extract import Page, extract, slugify
from ckb.docs.qa import detect_language
from ckb.docs.segment import numbered, prose
from ckb.schema import CKB_DIR
from scripts import docs_pipeline as dp


def make_pdf(pages: list[str]) -> bytes:
    """PDF mínimo (Helvetica, WinAnsi) com uma linha de texto por \\n; página vazia -> sem camada de texto."""
    objs = []

    def esc(s):
        return "".join(c if ord(c) < 128 else f"\\{ord(c.encode('latin-1')):03o}" for c in s).replace("(", "\\(").replace(")", "\\)")

    n = len(pages)
    objs.append("<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{' '.join(f'{3 + 2 * i} 0 R' for i in range(n))}] /Count {n} >>")
    for i, text in enumerate(pages):
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {4 + 2 * i} 0 R "
                    f"/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >> >> >> >>")
        lines = "".join(f"BT /F1 11 Tf 50 {740 - 16 * k} Td ({esc(l)}) Tj ET\n" for k, l in enumerate(text.split("\n")) if l)
        objs.append(f"<< /Length {len(lines.encode('latin-1'))} >>\nstream\n{lines}endstream")
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offs).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


class FakeOCR:
    def image_to_text(self, path):
        assert path.suffix == ".png"
        return "Texto lido por OCR na pagina em branco."


def test_extract_pdf_text_layer_and_ocr_fallback(tmp_path):
    f = tmp_path / "a.pdf"
    f.write_bytes(make_pdf(["Esta pagina tem camada de texto suficiente para ser aceita.\nSegunda linha.", ""]))
    pages = extract(f)
    assert pages[0].text.startswith("Esta pagina") and not pages[0].needs_ocr
    assert pages[1].needs_ocr
    pages = extract(f, ocr=FakeOCR())
    assert pages[1].ocr and "OCR" in pages[1].text


def test_clean_running_heads_hyphens_and_page_numbers():
    words = ["alfa", "beta", "gama", "delta", "epsilon", "zeta"]
    pages = [f"CATECISMO DA IGREJA {i}\n\nO homem {w} e uma crea-\ntura de Deus {w} que busca a verdade.\n\n{i + 10}" for i, w in enumerate(words)]
    cleaned = strip_running_heads(pages)
    assert all("CATECISMO" not in p and not p.strip().endswith(str(i + 10)) for i, p in enumerate(cleaned))
    assert paragraphs(cleaned[0]) == ["O homem alfa e uma creatura de Deus alfa que busca a verdade."]
    assert clean_document(["fim da frase sem ponto", "continua na outra pagina."]) == ["fim da frase sem ponto continua na outra pagina."]


def test_numbered_requires_increasing_numbers_and_keeps_continuations():
    paras = ["PRIMEIRA PARTE", "1. Deus infinitamente perfeito e bem-aventurado.", "Continuacao do paragrafo um.",
             "2. Para realizar o seu plano de amor, Deus enviou o seu Filho.", "Em 1962 o Concilio se reuniu em Roma e decidiu.",
             "3. O Filho encarnou-se para nos salvar de verdade."]
    out = numbered(paras, "CIC")
    assert [o["ref"] for o in out] == ["CIC 1", "CIC 2", "CIC 3"]
    assert "Continuacao" in out[0]["text"] and "1962" in out[1]["text"] and out[0]["section"] == "Primeira Parte"


def test_prose_windows_respect_paragraphs():
    paras = ["Titulo da Obra"] + [("Palavra " * 90).strip() + "." for _ in range(7)]
    out = prose(paras, "OBRA", target_words=200, max_words=300)
    assert len(out) >= 3 and all(len(o["text"].split()) <= 300 for o in out)
    assert out[0]["ref"] == "OBRA #1" and out[0]["section"] == "Titulo da Obra"


def test_language_detection_and_slug():
    assert detect_language("O homem não é o que os outros dizem que ele é, mas aquilo que ele faz com a sua vida")[0] == "pt"
    assert detect_language("Il Signore è il mio pastore e non manca nulla di ciò che mi serve per la vita")[0] == "it"
    assert slugify("Catecismo da Igreja Católica (1992).pdf") == "catecismo_da_igreja_catolica_1992_pdf"


def test_bible_book_detection_and_sequence_guided_verses():
    for t, osis in [("EVANGELHO SEGUNDO S. JOÃO", "John"), ("Epistola aos Romanos", "Rom"), ("Livro III dos Reis", "1Kgs"),
                    ("SEGUNDA EPISTOLA AOS CORINTHIOS", "2Cor"), ("Mathêus", "Matt"), ("Primeiro Livro dos Macabeus", "1Macc")]:
        assert detect_book(t) == osis
    assert detect_book("Era uma vez um homem. E disse") is None
    lines = ["CAPITULO I", "1 No principio. 2 Depois, em 1962 e 12 vezes. 3 Fim.", "CAPITULO II", "1 Outro. 3 Salto."]
    verses, issues = parse_book(lines)
    assert [(c, v) for c, v, _ in verses] == [(1, 1), (1, 2), (1, 3), (2, 1), (2, 3)]
    assert "1962" in verses[1][2] and any("não encontrado" in i for i in issues)  # 1962/12 não viram versículo


def _fixture_tree(tmp_path):
    root = tmp_path / "igreja"
    root.mkdir()
    (root / "Documento Numerado.pdf").write_bytes(make_pdf([
        "TITULO\n1. Deus infinitamente perfeito e bem-aventurado em si mesmo.\n2. Para realizar o seu plano de amor enviou o Filho.",
        "3. O Filho encarnou-se para nos salvar de verdade e para sempre."]))
    (root / "livro.txt").write_text("Capitulo Primeiro\n\n" + "\n\n".join(("Frase de prosa numero %d. " % i) * 12 for i in range(6)), encoding="utf-8")
    # Bíblia sintética: Jo 1 com o texto alemão do Allioli (CKB) como se fosse a tradução
    allioli = [json.loads(l) for l in (CKB_DIR / "corpus" / "allioli_de.jsonl").read_text(encoding="utf-8").splitlines()]
    jo = [r for r in allioli if r["canon_ref"].startswith("John.1.")]
    body = " ".join(f"{r['ref'].split(',')[1]} {r['text']}" for r in jo)
    (root / "Biblia Teste.txt").write_text(f"EVANGELHO SEGUNDO S. JOÃO\n\nCAPITULO I\n\n{body}\n", encoding="utf-8")
    return root, len(jo)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    ckb = tmp_path / "ckb"
    (ckb / "corpus").mkdir(parents=True)
    shutil.copy(CKB_DIR / "corpus" / "vulgata_clementina.jsonl", ckb / "corpus")
    shutil.copy(CKB_DIR / "sources.yaml", ckb)
    monkeypatch.setattr(dp, "CKB_DIR", ckb)
    monkeypatch.setattr(dp, "STAGING", ckb / "staging")
    return ckb


def test_scan_run_staging_and_promote(tmp_path, sandbox):
    root, n_jo = _fixture_tree(tmp_path)
    cat = tmp_path / "catalog.yaml"
    dp.scan(root, cat)
    data = yaml.safe_load(cat.read_text(encoding="utf-8"))
    by = {d["file"]: d for d in data["documents"]}
    assert len(by) == 3 and all(d["license_status"] == "verificar" for d in by.values())
    assert by["Biblia Teste.txt"]["kind"] == "bible" and by["Biblia Teste.txt"]["authority"] == "escritura"
    by["Biblia Teste.txt"]["language"] = "de"
    by["Documento Numerado.pdf"]["kind"] = "numbered"
    by["Documento Numerado.pdf"]["sigla"] = "DN"
    cat.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

    for e in data["documents"]:
        dp.run_entry(e, root, None)
    stg = sandbox / "staging"
    assert not (sandbox / "corpus" / "documento_numerado.jsonl").exists()  # sem licença -> staging
    num = [json.loads(l) for l in (stg / "documento_numerado.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["ref"] for r in num] == ["DN 1", "DN 2", "DN 3"]
    bible = [json.loads(l) for l in (stg / "biblia_teste.jsonl").read_text(encoding="utf-8").splitlines()]
    prov = json.loads((stg / "biblia_teste.provenance.json").read_text(encoding="utf-8"))
    qa = prov["pages"]["bible_qa"]["John"]
    assert len(bible) == n_jo == 51 and qa["verses_found_of_expected"] == 51 and 1 not in qa["missing"]  # cap. 1 completo
    assert 2 in qa["missing"] or "2" in qa["missing"]  # os demais capítulos aparecem como faltantes (QA funciona)
    assert sum(r["align"] == "identico" for r in bible) >= 40  # mesmo texto do Allioli -> alinha quase tudo

    with pytest.raises(SystemExit):  # sem evidência de licença não promove
        dp.promote("documento_numerado", cat)
    by["Documento Numerado.pdf"].update(license_status="livre", license_evidence="Teste: documento sintético, sem direitos.")
    cat.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    dp.run_entry(by["Documento Numerado.pdf"], root, None)  # agora com licença: grava direto no corpus
    assert (sandbox / "corpus" / "documento_numerado.jsonl").exists()


def test_ocr_backends(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from ckb.docs import extract as ex

    class StubClient:
        class messages:  # noqa: N801
            @staticmethod
            def create(**kw):
                img = kw["messages"][0]["content"][0]
                assert img["type"] == "image" and img["source"]["media_type"] == "image/png"
                return SimpleNamespace(content=[SimpleNamespace(type="text", text="1 No principio era o Verbo.")])

    png = tmp_path / "p.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert ex.ClaudeVisionOCR("pt", client=StubClient()).image_to_text(png) == "1 No principio era o Verbo."
    monkeypatch.setattr(ex.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="tesseract"):
        ex.TesseractOCR("pt")
    assert ex.get_ocr(None, "pt") is None
