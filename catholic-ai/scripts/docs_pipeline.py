"""Pipeline de documentos -> CKB.  scan -> (você revisa o catálogo) -> run -> promote.

  python -m scripts.docs_pipeline scan  PASTA  [--out catalog.local.yaml]
  python -m scripts.docs_pipeline run   catalog.local.yaml [--root PASTA] [--only ID] [--ocr tesseract|claude]
  python -m scripts.docs_pipeline promote ID catalog.local.yaml

scan    percorre a pasta e gera um catálogo (YAML) com palpites de idioma/tipo/sigla e `license_status: verificar`.
run     extrai (PDF com camada de texto; OCR por página se configurado), limpa, segmenta e grava JSONL.
        Sem licença confirmada o resultado vai para ckb/staging/ (ignorado pelo git), NUNCA para ckb/corpus/.
promote registra a fonte em sources.yaml e move staging -> corpus; exige license_status livre/licenciado e
        `license_evidence` preenchida (de onde vem o direito de usar o texto).
Tipos (`kind`): numbered (parágrafos numerados: CIC, encíclicas), prose (texto corrido), bible (Bíblia em um ou
vários livros; alinha à Vulgata e confere versículos por capítulo).
"""
import argparse
import json
import re
import sys
from pathlib import Path

import yaml

from ckb.align import classify_book
from ckb.docs import bible as bib
from ckb.docs.clean import clean_document
from ckb.docs.extract import SUPPORTED, extract, get_ocr, sha256_file, slugify
from ckb.docs.qa import detect_language, page_report
from ckb.docs.segment import numbered, prose
from ckb.languages import LANGUAGES
from ckb.schema import CKB_DIR, INGESTABLE, Passage, load_registry
from ckb.verify import filter_alignments
from scripts.convert_scrollmapper_bible import BOOKS, OSIS

OSIS_TO_ABBR = {osis: BOOKS[name] for name, osis in OSIS.items()}
OSIS_TO_NAME = {osis: name for name, osis in OSIS.items()}
STAGING = CKB_DIR / "staging"
GUESS_KIND = [(r"b[ií]blia|bibbia|biblia|vulgata|testament", "bible"),
              (r"catecismo|catechism|catechismo|enc[ií]clica|enciclica|exorta|constitui|decreto|declara|concílio|concilio|lumen|gaudium|encyclical", "numbered")]
GUESS_AUTH = [(r"b[ií]blia|bibbia|biblia|vulgata|testament", "escritura"),
              (r"padre|agostinho|augustin|jerônimo|crisóstomo|atanásio|basílio|gregório|orígenes", "padres"),
              (r"aquino|suma|summa|bernardo|boaventura|teresa|joão da cruz", "teologo")]


def guess(patterns, name: str, default: str) -> str:
    for rx, val in patterns:
        if re.search(rx, name, re.I):
            return val
    return default


def scan(root: Path, out: Path) -> None:
    entries, seen = [], set()
    for f in sorted(root.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in SUPPORTED or f.name.startswith("."):
            continue
        sid = slugify(f.stem)
        while sid in seen:
            sid += "_2"
        seen.add(sid)
        try:
            pages = extract(f)[:3]
            sample = " ".join(p.text for p in pages)
            lang, score = detect_language(sample)
            has_text = any(len(p.text.strip()) > 40 for p in pages)
        except Exception as e:  # noqa: BLE001 - arquivo corrompido não pode parar a varredura
            lang, score, has_text = "?", 0.0, False
            print(f"  aviso: {f.name}: {e}", file=sys.stderr)
        entries.append({
            "file": str(f.relative_to(root)), "source_id": sid, "title": f.stem,
            "language": lang if lang in LANGUAGES else "pt", "guessed_language": f"{lang} ({score})",
            "authority": guess(GUESS_AUTH, f.stem, "magisterio"), "kind": guess(GUESS_KIND, f.stem, "prose"),
            "sigla": re.sub(r"[^A-Za-z0-9]", "", "".join(w[0] for w in f.stem.split() if w[0].isalpha()).upper())[:6] or "DOC",
            "scheme": "vulgata", "layout": False, "ocr": None if has_text else "tesseract",
            "has_text_layer": has_text, "size_kb": round(f.stat().st_size / 1024), "sha256": sha256_file(f),
            "license_status": "verificar", "license_evidence": "", "skip": False, "notes": "",
        })
    out.write_text("# REVISE cada entrada: kind, sigla, authority, license_status/license_evidence, skip.\n"
                   + yaml.safe_dump({"root": str(root), "documents": entries}, allow_unicode=True, sort_keys=False),
                   encoding="utf-8")
    print(f"{len(entries)} documentos -> {out}")


def load_latin():
    lens, text = {}, {}
    for line in (CKB_DIR / "corpus" / "vulgata_clementina.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        b, c, v = r["canon_ref"].split(".")
        lens.setdefault(b, []).append(((int(c), int(v)), sum(ch.isalpha() for ch in r["text"])))
        text[r["canon_ref"]] = r["text"]
    return lens, text


def run_bible(paras: list[str], e: dict) -> tuple[list[dict], dict]:
    books = bib.split_books(paras, e.get("scheme", "vulgata"))
    if e.get("book"):  # arquivo de um livro só (sem título detectável)
        books = {e["book"]: paras}
    latin, latin_text = load_latin()
    rows, qa = [], {}
    for osis, lines in books.items():
        verses, issues = bib.parse_book(lines)
        counts: dict[int, int] = {}
        for (c, v), _ in latin.get(osis, []):
            counts[c] = max(counts.get(c, 0), v)
        qa[osis] = {**bib.qa_counts(verses, counts), "issues": issues[:10]}
        if not verses:
            continue
        if osis in latin:
            chaps = {c for c, _, _ in verses}  # só os capítulos presentes: OCR parcial não pode desalinhar o resto
            res, qs = classify_book([(c, v) for c, v, _ in verses], [sum(ch.isalpha() for ch in t) for _, _, t in verses],
                                    [x for x in latin[osis] if x[0][0] in chaps])
        else:
            res, qs = [{"refs": [], "label": ""}] * len(verses), {}
        qa[osis]["alignment"] = qs
        for (c, v, text), a in zip(verses, res):
            refs = [f"{osis}.{cc}.{vv}" for cc, vv in a["refs"]]
            rows.append({"source_id": e["source_id"], "canon_ref": refs[0] if refs else "",
                         "canon_ref_2": refs[1] if len(refs) > 1 else "", "align": a["label"],
                         "ref": f"{OSIS_TO_ABBR[osis]} {c},{v}", "text": text,
                         "section": f"{OSIS_TO_NAME[osis]} {c}", "language": e["language"]})
    rows, filt = filter_alignments(rows, latin_text, script="latin")
    qa["_name_audit"] = {"dropped": filt["dropped"]}
    return rows, qa


def run_entry(e: dict, root: Path, ocr_override: str | None) -> dict:
    path = root / e["file"]
    ocr = get_ocr(ocr_override or e.get("ocr"), e["language"])
    pages = extract(path, ocr=ocr, layout=e.get("layout", False))
    rep = page_report(pages)
    paras = clean_document([p.text for p in pages])
    lang, score = detect_language(" ".join(paras)[:20000])
    rep["detected_language"] = f"{lang} ({score})"
    kind = e["kind"]
    if kind == "bible":
        rows, qa = run_bible(paras, e)
        rep["bible_qa"] = qa
    else:
        segs = (numbered if kind == "numbered" else prose)(paras, e.get("sigla", "DOC"))
        seen, rows = set(), []
        for s in segs:
            ref = s["ref"]
            if ref in seen:
                ref = f"{ref}-{len(seen)}"
            seen.add(ref)
            rows.append({"source_id": e["source_id"], "ref": ref, "text": s["text"], "section": s["section"],
                         "language": e["language"]})
    rows = [Passage(**r).model_dump() for r in rows]  # valida o esquema
    ok = e["license_status"] in INGESTABLE and bool(e.get("license_evidence", "").strip())
    out = (CKB_DIR / "corpus" if ok else STAGING) / f"{e['source_id']}.jsonl"
    out.parent.mkdir(exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    prov = {"source_id": e["source_id"], "file": e["file"], "sha256": sha256_file(path), "kind": kind,
            "passages": len(rows), "pages": rep, "license_status": e["license_status"],
            "license_evidence": e.get("license_evidence", "")}
    out.with_suffix(".provenance.json").write_text(json.dumps(prov, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{e['source_id']}: {len(rows)} trechos ({kind}) -> {out.relative_to(CKB_DIR.parent)}"
          f"{'' if ok else '  [STAGING: licença não confirmada]'}")
    if rep["pages_needing_ocr"]:
        print(f"   ! {len(rep['pages_needing_ocr'])} páginas sem texto; use --ocr tesseract|claude")
    if lang != e["language"] and score > 0.05:
        print(f"   ! idioma detectado {lang} ≠ declarado {e['language']}")
    return prov


def promote(source_id: str, catalog: Path) -> None:
    cat = yaml.safe_load(catalog.read_text(encoding="utf-8"))
    e = next(d for d in cat["documents"] if d["source_id"] == source_id)
    if e["license_status"] not in INGESTABLE or not e.get("license_evidence", "").strip():
        raise SystemExit("promote exige license_status livre|licenciado E license_evidence preenchida")
    if source_id in load_registry():
        print("já registrada em sources.yaml")
    else:
        stanza = (f"\n  - id: {source_id}\n    title: {json.dumps(e['title'], ensure_ascii=False)}\n"
                  f"    authority: {e['authority']}\n    language: {e['language']}\n"
                  f"    license_status: {e['license_status']}\n"
                  f"    license_note: {json.dumps(e['license_evidence'], ensure_ascii=False)}\n"
                  f"    ref_format: \"{e.get('sigla', '')}\"\n")
        with (CKB_DIR / "sources.yaml").open("a", encoding="utf-8") as f:
            f.write(stanza)
    for ext in (".jsonl", ".provenance.json"):
        src = STAGING / f"{source_id}{ext}"
        if src.exists():
            src.replace(CKB_DIR / "corpus" / src.name)
    print(f"{source_id} promovida. Próximo: python -m scripts.ckb_validate && python -m scripts.ingest {source_id}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("scan"); a.add_argument("root"); a.add_argument("--out", default="catalog.local.yaml")
    r = sub.add_parser("run"); r.add_argument("catalog"); r.add_argument("--root"); r.add_argument("--only")
    r.add_argument("--ocr", choices=["tesseract", "claude"])
    p = sub.add_parser("promote"); p.add_argument("source_id"); p.add_argument("catalog")
    args = ap.parse_args()
    if args.cmd == "scan":
        scan(Path(args.root), Path(args.out))
    elif args.cmd == "run":
        cat = yaml.safe_load(Path(args.catalog).read_text(encoding="utf-8"))
        root = Path(args.root or cat["root"])
        for e in cat["documents"]:
            if e.get("skip") or (args.only and e["source_id"] != args.only):
                continue
            try:
                run_entry(e, root, args.ocr)
            except Exception as ex:  # noqa: BLE001 - um documento ruim não derruba o lote
                print(f"{e['source_id']}: ERRO {type(ex).__name__}: {ex}", file=sys.stderr)
    else:
        promote(args.source_id, Path(args.catalog))


if __name__ == "__main__":
    main()
