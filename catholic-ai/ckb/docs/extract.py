"""Extração de texto de documentos: PDF (camada de texto + OCR por página), DOCX, EPUB, HTML, TXT, ODT/RTF, imagens."""
import hashlib
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

SUPPORTED = {".pdf", ".txt", ".md", ".html", ".htm", ".docx", ".epub", ".odt", ".rtf", ".doc",
             ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
IMAGES = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
TESS_LANG = {"pt": "por", "it": "ita", "es": "spa", "fr": "fra", "de": "deu", "en": "eng", "la": "lat",
             "grc": "grc", "hbo": "heb"}


@dataclass
class Page:
    n: int
    text: str
    ocr: bool = False
    needs_ocr: bool = False  # página sem texto e nenhum OCR configurado


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class TesseractOCR:
    """OCR local (binário `tesseract` + pacotes de idioma, ex.: por/ita/spa/lat)."""

    def __init__(self, lang: str):
        if not shutil.which("tesseract"):
            raise RuntimeError("tesseract não encontrado (instale tesseract-ocr e os idiomas necessários)")
        self.lang = TESS_LANG.get(lang, lang)

    def image_to_text(self, path: Path) -> str:
        r = subprocess.run(["tesseract", str(path), "stdout", "-l", self.lang, "--psm", "1"],
                           capture_output=True, check=True)
        return r.stdout.decode("utf-8", "replace")


class ClaudeVisionOCR:
    """OCR por visão do Claude (API da Anthropic) — bom em páginas antigas; custa tokens por página."""

    PROMPT = ("Transcreva fielmente TODO o texto desta página, na língua original, preservando a numeração de "
              "capítulos, versículos e parágrafos. Não traduza, não corrija a ortografia antiga, não resuma e "
              "não comente. Omita cabeçalhos correntes, rodapés e números de página. Se houver colunas, leia "
              "uma coluna por vez. Responda só com o texto.")

    def __init__(self, lang: str, model: str = "claude-sonnet-5-5", client=None):
        import anthropic

        self.client = client or anthropic.Anthropic()
        self.model, self.lang = model, lang

    def image_to_text(self, path: Path) -> str:
        import base64

        media = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(path.suffix.lower(), "image/png")
        data = base64.b64encode(path.read_bytes()).decode()
        msg = self.client.messages.create(
            model=self.model, max_tokens=4000,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}},
                {"type": "text", "text": self.PROMPT}]}])
        return "".join(b.text for b in msg.content if b.type == "text")


def get_ocr(name: str | None, lang: str):
    if not name:
        return None
    return {"tesseract": TesseractOCR, "claude": ClaudeVisionOCR}[name](lang)


def _pdf_pages(path: Path, layout: bool) -> list[str]:
    cmd = ["pdftotext", "-enc", "UTF-8"] + (["-layout"] if layout else []) + [str(path), "-"]
    out = subprocess.run(cmd, capture_output=True, check=True).stdout.decode("utf-8", "replace")
    pages = out.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def _render_page(path: Path, n: int, tmp: Path) -> Path:
    subprocess.run(["pdftoppm", "-r", "300", "-f", str(n), "-l", str(n), "-png", str(path), str(tmp / "p")],
                   check=True, capture_output=True)
    return sorted(tmp.glob("p-*.png"))[0]


def _html_text(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style"]):
        t.decompose()
    for br in soup.find_all(["br"]):
        br.replace_with("\n")
    blocks = [b.get_text(" ", strip=True) for b in soup.find_all(["p", "h1", "h2", "h3", "h4", "li", "div"])
              if not b.find(["p", "h1", "h2", "h3", "h4", "li", "div"])]
    return "\n\n".join(b for b in blocks if b) or soup.get_text("\n")


def _soffice_txt(path: Path) -> str:
    if shutil.which("pandoc") and path.suffix.lower() in {".odt", ".rtf", ".docx"}:
        return subprocess.run(["pandoc", str(path), "-t", "plain", "--wrap=none"], capture_output=True,
                              check=True).stdout.decode("utf-8", "replace")
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["soffice", "--headless", "--convert-to", "txt:Text", "--outdir", d, str(path)],
                       check=True, capture_output=True)
        return next(Path(d).glob("*.txt")).read_text(encoding="utf-8", errors="replace")


def extract(path: Path, ocr=None, min_chars: int = 40, layout: bool = False) -> list[Page]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        pages = []
        with tempfile.TemporaryDirectory() as d:
            for i, text in enumerate(_pdf_pages(path, layout), 1):
                if len(text.strip()) >= min_chars:
                    pages.append(Page(i, text))
                elif ocr:
                    for old in Path(d).glob("p-*.png"):
                        old.unlink()
                    pages.append(Page(i, ocr.image_to_text(_render_page(path, i, Path(d))), ocr=True))
                else:
                    pages.append(Page(i, text, needs_ocr=True))
        return pages
    if ext in IMAGES:
        return [Page(1, ocr.image_to_text(path), ocr=True)] if ocr else [Page(1, "", needs_ocr=True)]
    if ext in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        return [Page(i, t) for i, t in enumerate(text.split("\f"), 1) if t.strip()]
    if ext in {".html", ".htm"}:
        return [Page(1, _html_text(path.read_text(encoding="utf-8", errors="replace")))]
    if ext == ".epub":
        with zipfile.ZipFile(path) as z:
            names = sorted(n for n in z.namelist() if n.lower().endswith((".xhtml", ".html", ".htm")))
            return [Page(i, _html_text(z.read(n).decode("utf-8", "replace"))) for i, n in enumerate(names, 1)]
    if ext == ".docx":
        import docx

        return [Page(1, "\n\n".join(p.text for p in docx.Document(str(path)).paragraphs if p.text.strip()))]
    if ext in {".odt", ".rtf", ".doc"}:
        return [Page(1, _soffice_txt(path))]
    raise ValueError(f"formato não suportado: {ext}")


_RX = re.compile(r"[^\w]+")


def slugify(name: str) -> str:
    import unicodedata

    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return _RX.sub("_", s).strip("_")[:60] or "doc"
