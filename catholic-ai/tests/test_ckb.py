import json

import pytest

from ckb.schema import INGESTABLE, Passage, load_passages, load_registry


def test_registry_loads_and_gates_licenses():
    reg = load_registry()
    assert reg["cic"].license_status == "verificar" and not reg["cic"].ingestable
    assert reg["biblia_almeida_arc"].license_status == "bloqueado"
    assert reg["vulgata_clementina"].license_status in INGESTABLE


def test_passage_normalizes_whitespace_and_rejects_blank():
    p = Passage(source_id="x", ref="a", text="uma   frase\n com espaços   estranhos ok")
    assert p.text == "uma frase com espaços estranhos ok"
    with pytest.raises(Exception):
        Passage(source_id="x", ref="a", text="   ")


def test_duplicate_ref_rejected(tmp_path):
    row = {"source_id": "s", "ref": "r1", "text": "texto longo o suficiente para valer"}
    (tmp_path / "s.jsonl").write_text(json.dumps(row) + "\n" + json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicada"):
        load_passages("s", tmp_path)
