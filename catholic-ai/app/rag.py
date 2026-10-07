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
            passages.append(
                Passage(doc, meta["ref"], meta["source"], meta.get("authority", ""), score)
            )
    return passages


def format_sources(passages: list[Passage]) -> str:
    blocks = [
        f'[{i}] ({p.authority}) {p.source} — {p.ref}\n{p.text}' for i, p in enumerate(passages, 1)
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

    client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
    user_msg = f"{format_sources(passages)}\n\nPergunta do usuário: {question}"
    msg = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=700,
        system=SYSTEM_PROMPT,
        messages=[*history, {"role": "user", "content": user_msg}],
    )
    return "".join(b.text for b in msg.content if b.type == "text")
