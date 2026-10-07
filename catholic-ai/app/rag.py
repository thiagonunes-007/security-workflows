from dataclasses import dataclass

import anthropic
import chromadb
from chromadb.utils import embedding_functions

from .config import Settings
from .prompts import NO_GROUNDING, SYSTEM_PROMPT

COLLECTION = "fontes_catolicas"


@dataclass
class Passage:
    text: str
    ref: str  # ex.: "CIC §1213", "Jo 3,16"
    source: str  # ex.: "Catecismo da Igreja Católica"
    authority: str  # ex.: "escritura", "magisterio", "padres", "teologo"
    score: float
    canon_ref: str = ""  # chave neutra de idioma (John.3.16, CIC.1213)
    language: str = ""
    aligned: bool = False  # True = trazido por alinhamento, não pela busca semântica
    align: str = ""  # qualidade do alinhamento (ver ckb.schema.Passage.align)


def get_collection(settings: Settings):
    client = chromadb.PersistentClient(path=settings.chroma_path)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=settings.embedding_model)
    return client.get_or_create_collection(
        COLLECTION, embedding_function=ef, metadata={"hnsw:space": "cosine"}
    )


def retrieve(collection, question: str, settings: Settings) -> list[Passage]:
    res = collection.query(query_texts=[question], n_results=settings.top_k)
    passages = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        score = 1.0 - dist  # distância cosseno -> similaridade
        if score >= settings.min_score:
            passages.append(_to_passage(doc, meta, score))
    return passages


def _to_passage(doc: str, meta: dict, score: float, aligned: bool = False) -> Passage:
    # o índice guarda texto normalizado (grego sem acentos, hebraico sem niqqud);
    # exibimos o original quando existir
    return Passage(
        meta.get("original") or doc, meta["ref"], meta["source"], meta.get("authority", ""),
        score, meta.get("canon_ref", ""), meta.get("language", ""), aligned, meta.get("align", ""),
    )


MAX_ALIGNED = 12


def expand_aligned(collection, passages: list[Passage], langs: list[str]) -> list[Passage]:
    """Anexa o MESMO trecho em outras línguas (ex.: grego/hebraico/latim) via canon_ref."""
    refs = sorted({p.canon_ref for p in passages if p.canon_ref})
    if not refs or not langs:
        return []
    res = collection.get(
        where={"$and": [
            {"$or": [{"canon_ref": {"$in": refs}}, {"canon_ref_2": {"$in": refs}}]},
            {"language": {"$in": langs}},
        ]},
        limit=MAX_ALIGNED,
    )
    have = {(p.ref, p.source) for p in passages}
    out = []
    for doc, meta in zip(res["documents"], res["metadatas"]):
        if (meta["ref"], meta["source"]) not in have:
            out.append(_to_passage(doc, meta, 0.0, aligned=True))
    return out


def format_sources(passages: list[Passage]) -> str:
    blocks = [
        f'[{i}] ({p.authority}, {p.language or "?"}{", alinhado" if p.aligned else ""}'
        f'{", alinhamento incerto" if p.align == "incerto" else ""}) '
        f'{p.source} — {p.ref}\n{p.text}'
        for i, p in enumerate(passages, 1)
    ]
    return "<fontes>\n" + "\n\n".join(blocks) + "\n</fontes>"


def answer(
    question: str,
    history: list[dict],
    collection,
    settings: Settings,
    client: anthropic.Anthropic | None = None,
) -> str:
    passages = retrieve(collection, question, settings)
    if not passages:
        return NO_GROUNDING  # sem fundamento: nem chama o LLM

    langs = [x.strip() for x in settings.context_languages.split(",") if x.strip()]
    passages = passages + expand_aligned(collection, passages, langs)

    client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
    user_msg = f"{format_sources(passages)}\n\nPergunta do usuário: {question}"
    msg = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=700,
        system=SYSTEM_PROMPT,
        messages=[*history, {"role": "user", "content": user_msg}],
    )
    return "".join(b.text for b in msg.content if b.type == "text")
