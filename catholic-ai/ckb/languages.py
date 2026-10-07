"""Idiomas do CKB e normalização de texto para busca."""
import unicodedata

# código -> (nome, direção). 'grc' = grego antigo/koiné; 'hbo' = hebraico bíblico.
LANGUAGES = {
    "grc": ("Grego (koiné/LXX/NT)", "ltr"),
    "hbo": ("Hebraico bíblico", "rtl"),
    "la": ("Latim", "ltr"),
    "pt": ("Português", "ltr"),
    "en": ("Inglês", "ltr"),
    "it": ("Italiano", "ltr"),
    "de": ("Alemão", "ltr"),
    "es": ("Espanhol", "ltr"),
    "fr": ("Francês", "ltr"),
}


def normalize_for_search(text: str, lang: str) -> str:
    """Versão do texto usada no EMBEDDING. O texto original é sempre preservado para exibição.

    - hbo: remove cantilação e vocalização (niqqud), maqaf vira espaço.
    - grc: remove acentos e espíritos, minúsculas, sigma final -> sigma.
    - la: ligaduras æ/œ viram ae/oe (a Vulgata Clementina usa "cælum", "tenebræ").
    - demais: apenas NFC e espaços normalizados.
    """
    t = unicodedata.normalize("NFC", text)
    if lang == "hbo":
        t = t.replace("־", " ")
        t = "".join(c for c in unicodedata.normalize("NFD", t) if not "֑" <= c <= "ׇ")
    elif lang == "la":
        for a, b in (("æ", "ae"), ("Æ", "Ae"), ("œ", "oe"), ("Œ", "Oe")):
            t = t.replace(a, b)
    elif lang == "grc":
        t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
        t = unicodedata.normalize("NFC", t.lower().replace("ς", "σ"))
    return " ".join(t.split())
