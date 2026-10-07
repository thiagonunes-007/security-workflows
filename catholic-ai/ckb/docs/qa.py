"""Controle de qualidade de documentos extraídos: idioma, lixo de OCR, páginas problemáticas."""
import re

STOP = {
    "pt": "de a o que e do da em um para é com não uma os no se na por mais as dos como mas foi ao ele das tem à seu sua ou",
    "es": "de la que el en y a los del se las por un para con no una su al lo como más pero sus le ya o este sí porque",
    "it": "di e il la che in a per un del è una non le si con da dei come più ma al ha sono lo nel gli della ai",
    "fr": "de la le et les des en un du une que est pour qui dans a par plus pas au sur se ne sont avec il ce son",
    "de": "der die und in den von zu das mit sich des auf für ist im dem nicht ein eine als auch es an werden aus er",
    "en": "the of and to in a is that for it as was with be by on not he this are or his from at which but have an",
    "la": "et in est non ad ut cum qui quae quod sed de per ex a ab esse sunt eius enim autem si nec tu me",
}
STOPSETS = {k: set(v.split()) for k, v in STOP.items()}


def detect_language(text: str) -> tuple[str, float]:
    toks = re.findall(r"[^\W\d_]+", text.lower())[:4000]
    if not toks:
        return "?", 0.0
    scores = {k: sum(t in s for t in toks) / len(toks) for k, s in STOPSETS.items()}
    best = max(scores, key=scores.get)
    return best, round(scores[best], 3)


def garbage_ratio(text: str) -> float:
    """Fração de caracteres que não são letras, dígitos, espaço ou pontuação comum (sinal de OCR ruim)."""
    if not text:
        return 0.0
    bad = sum(1 for c in text if not (c.isalnum() or c.isspace() or c in ".,;:!?'’\"“”«»()[]-–—/·§¶%&*…"))
    return round(bad / len(text), 4)


def page_report(pages) -> dict:
    texts = [p.text for p in pages]
    return {
        "pages": len(pages),
        "ocr_pages": sum(p.ocr for p in pages),
        "pages_needing_ocr": [p.n for p in pages if p.needs_ocr],
        "empty_pages": [p.n for p in pages if not p.text.strip() and not p.needs_ocr],
        "garbage_ratio": garbage_ratio("\n".join(texts)),
        "avg_chars_per_page": round(sum(len(t) for t in texts) / max(1, len(texts))),
    }
