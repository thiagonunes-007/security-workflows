import hashlib
import hmac

from app import whatsapp


def sign(secret, body):
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_signature_ok_and_bad():
    body = b'{"a":1}'
    assert whatsapp.verify_signature("s", body, sign("s", body))
    assert not whatsapp.verify_signature("s", body, sign("outro", body))
    assert not whatsapp.verify_signature("s", body, None)
    assert not whatsapp.verify_signature("", body, sign("", body))


def test_parse_messages_ignores_non_text():
    payload = {"entry": [{"changes": [{"value": {"messages": [
        {"id": "1", "from": "551199", "type": "text", "text": {"body": "oi"}},
        {"id": "2", "from": "551199", "type": "image"},
    ]}}]}]}
    assert whatsapp.parse_messages(payload) == [{"id": "1", "from": "551199", "text": "oi"}]


def test_split_text_respects_limit():
    text = "\n\n".join(["palavra " * 300] * 5)
    parts = whatsapp.split_text(text, limit=1000)
    assert all(len(p) <= 1000 for p in parts)
    assert "".join(parts).replace("\n", "").replace(" ", "") == text.replace("\n", "").replace(" ", "")
