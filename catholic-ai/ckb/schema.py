"""Esquema do CKB: registro de fontes + trechos (passages)."""
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

CKB_DIR = Path(__file__).parent
Authority = Literal["escritura", "magisterio", "padres", "teologo"]
License = Literal["livre", "licenciado", "verificar", "bloqueado"]
INGESTABLE = {"livre", "licenciado"}


class Source(BaseModel):
    id: str
    title: str
    authority: Authority
    language: str
    license_status: License
    license_note: str = ""
    ref_format: str = ""

    @property
    def ingestable(self) -> bool:
        return self.license_status in INGESTABLE


class Passage(BaseModel):
    """Uma unidade citável: versículo, parágrafo do CIC, artigo da Suma..."""

    source_id: str
    ref: str = Field(min_length=1)  # ex.: "CIC §1213"
    text: str
    section: str = ""  # breadcrumb opcional: "Parte I > Seção 2"
    language: str = ""

    @field_validator("text")
    @classmethod
    def no_blank(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("texto vazio")
        return v


def load_registry(path: Path = CKB_DIR / "sources.yaml") -> dict[str, Source]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))["sources"]
    reg = {s["id"]: Source(**s) for s in raw}
    if len(reg) != len(raw):
        raise ValueError("ids de fonte duplicados em sources.yaml")
    return reg


def load_passages(source_id: str, corpus_dir: Path = CKB_DIR / "corpus") -> list[Passage]:
    path = corpus_dir / f"{source_id}.jsonl"
    out, seen = [], set()
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        p = Passage(**json.loads(line))
        if p.source_id != source_id:
            raise ValueError(f"{path.name}:{n} source_id '{p.source_id}' != '{source_id}'")
        if p.ref in seen:
            raise ValueError(f"{path.name}:{n} ref duplicada: {p.ref}")
        seen.add(p.ref)
        out.append(p)
    return out
