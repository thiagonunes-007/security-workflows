import hashlib
import json
import logging
import time
from collections import OrderedDict, defaultdict, deque

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response

from . import rag, whatsapp
from .config import get_settings
from .prompts import WELCOME

log = logging.getLogger("catholic-ai")
app = FastAPI(title="Catholic AI")
settings = get_settings()

_collection = None
_seen: OrderedDict[str, None] = OrderedDict()  # dedup de message ids (Meta reenvia)
_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=6))
_hits: dict[str, deque] = defaultdict(deque)
RATE_LIMIT, RATE_WINDOW = 10, 60  # 10 msgs/min por usuário


def collection():
    global _collection
    if _collection is None:
        _collection = rag.get_collection(settings)
    return _collection


def user_key(phone: str) -> str:
    """Não guardamos o número em claro (LGPD)."""
    return hashlib.sha256((settings.phone_hash_salt + phone).encode()).hexdigest()[:16]


def rate_limited(key: str) -> bool:
    now, q = time.time(), _hits[key]
    while q and now - q[0] > RATE_WINDOW:
        q.popleft()
    q.append(now)
    return len(q) > RATE_LIMIT


def handle(msg: dict) -> None:
    key = user_key(msg["from"])
    send = lambda t: whatsapp.send_text(
        settings.whatsapp_token, settings.whatsapp_phone_number_id, msg["from"], t
    )
    try:
        text = msg["text"].strip()
        if text.lower() in {"oi", "olá", "ola", "ajuda", "menu", "start"}:
            return send(WELCOME)
        if rate_limited(key):
            return send("Muitas mensagens seguidas. Aguarde um minuto, por favor. 🙏")
        hist = list(_history[key])
        reply = rag.answer(text, hist, collection(), settings)
        _history[key].extend([{"role": "user", "content": text}, {"role": "assistant", "content": reply}])
        send(reply)
    except Exception:
        log.exception("falha ao responder")
        send("Desculpe, tive um problema técnico. Tente novamente em instantes.")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/webhook")
def verify(request: Request):
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == settings.whatsapp_verify_token:
        return Response(q.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(403)


@app.post("/webhook")
async def receive(request: Request, tasks: BackgroundTasks):
    body = await request.body()
    if not whatsapp.verify_signature(
        settings.whatsapp_app_secret, body, request.headers.get("X-Hub-Signature-256")
    ):
        raise HTTPException(403, "assinatura inválida")
    for msg in whatsapp.parse_messages(json.loads(body)):
        if msg["id"] in _seen:
            continue
        _seen[msg["id"]] = None
        if len(_seen) > 5000:
            _seen.popitem(last=False)
        tasks.add_task(handle, msg)  # responde 200 rápido; processa em background
    return {"status": "ok"}
