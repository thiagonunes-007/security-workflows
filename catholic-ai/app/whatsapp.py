import hashlib
import hmac

import httpx

GRAPH_URL = "https://graph.facebook.com/v21.0"
MAX_LEN = 3800  # limite do WhatsApp é 4096


def verify_signature(app_secret: str, body: bytes, header: str | None) -> bool:
    """Valida X-Hub-Signature-256 enviado pela Meta."""
    if not app_secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def parse_messages(payload: dict) -> list[dict]:
    """Extrai mensagens de texto recebidas: [{id, from, text}]."""
    out = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for m in change.get("value", {}).get("messages", []):
                if m.get("type") == "text":
                    out.append({"id": m["id"], "from": m["from"], "text": m["text"]["body"]})
    return out


def split_text(text: str, limit: int = MAX_LEN) -> list[str]:
    parts, cur = [], ""
    for para in text.split("\n\n"):
        while len(para) > limit:  # parágrafo gigante: corta por espaço
            cut = para.rfind(" ", 0, limit)
            if cut <= 0:
                cut = limit
            parts.append(para[:cut])
            para = para[cut:].lstrip()
        if len(cur) + len(para) + 2 > limit and cur:
            parts.append(cur)
            cur = para
        else:
            cur = f"{cur}\n\n{para}" if cur else para
    if cur:
        parts.append(cur)
    return parts


def send_text(token: str, phone_number_id: str, to: str, text: str) -> None:
    for part in split_text(text):
        r = httpx.post(
            f"{GRAPH_URL}/{phone_number_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": part}},
            timeout=15,
        )
        r.raise_for_status()
