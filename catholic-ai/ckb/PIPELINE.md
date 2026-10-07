# Pipeline de documentos → CKB

Para PDFs, livros digitalizados e documentos que você já tem (pasta `igreja/`). Uma etapa por comando;
você revisa o catálogo antes de qualquer coisa entrar no corpus.

```
scan  →  catalog.local.yaml  →  (você revisa)  →  run  →  ckb/staging/  →  promote  →  ckb/corpus/
```

```bash
python -m scripts.docs_pipeline scan igreja/ --out catalog.local.yaml
# edite o catálogo: kind, sigla, authority, language, skip, license_status + license_evidence
python -m scripts.docs_pipeline run catalog.local.yaml --root igreja/ [--only ID] [--ocr tesseract|claude]
python -m scripts.docs_pipeline promote ID catalog.local.yaml      # só com licença + evidência
python -m scripts.ckb_validate && python -m scripts.ingest ID
```

## O que cada etapa faz
| Etapa | Detalhes |
|---|---|
| **extract** | PDF (camada de texto via `pdftotext`; página sem texto → OCR se configurado), DOCX, EPUB, HTML, TXT, ODT/RTF/DOC, imagens |
| **OCR** | `tesseract` local (instale `tesseract-ocr` + idiomas `por ita spa lat ...`) ou `claude` (visão, API da Anthropic; melhor em páginas antigas, custa tokens por página) |
| **clean** | ligaduras (ﬁ, ſ), hifenização, cabeçalhos/rodapés repetidos, números de página, parágrafo que atravessa a página |
| **segment** | `numbered` (um trecho por parágrafo numerado: CIC, encíclicas, Vaticano II), `prose` (janelas de ~220 palavras por parágrafo inteiro), `bible` |
| **bible** | acha livros (tolera "Mathêus", "Esther", "SEGUNDA EPISTOLA AOS CORINTHIOS"), capítulos e versículos guiados pela sequência 1,2,3…; alinha à Vulgata (comprimento + auditoria por nomes); confere versículos por capítulo contra a Vulgata |
| **QA** | idioma detectado × declarado, páginas sem texto, taxa de lixo de OCR, cobertura de versículos |

## Regras de segurança (não são opcionais)
- **Nada vai para `ckb/corpus/` sem `license_status` livre/licenciado e `license_evidence` preenchida.**
  O resto fica em `ckb/staging/` (ignorado pelo git, para não publicar texto com direitos).
- O catálogo (`catalog*.local.yaml`) também é ignorado pelo git.
- O pipeline nunca muda `license_status` sozinho.

## Bíblias digitalizadas (pt/it/es)
Use `kind: bible`. Para Vulgata antiga o esquema de Reis é `scheme: vulgata` (1–4 Reis = 1–2 Sm, 1–2 Rs); para
traduções modernas, `modern`. O relatório (`*.provenance.json` → `pages.bible_qa`) lista, por livro, capítulos
e versículos faltantes e o que passa da Vulgata. **Cobertura abaixo de ~97% = revisar o OCR antes de promover.**
Um livro em arquivo separado, sem título detectável, pode usar `book: John` (id OSIS) na entrada do catálogo.

## Limites conhecidos
- Sem `tesseract` neste ambiente de desenvolvimento, o OCR foi testado só com backends simulados; teste um
  PDF escaneado real no seu computador antes de confiar em lotes grandes.
- A detecção de títulos de livro é heurística: confira `books_found` x esperado nos relatórios.
- Colunas duplas: `layout: false` (padrão) deixa o `pdftotext` ordenar a leitura; se embaralhar, tente `layout: true` ou `--ocr claude`.
- Notas de rodapé e comentários no mesmo fluxo do texto contaminam versículos; a conferência com a Vulgata ajuda a achar.

## Dependências do sistema
`poppler-utils` (`pdftotext`, `pdftoppm`) é obrigatório para PDF. Opcionais: `pandoc`/`libreoffice` (ODT, RTF, DOC),
`tesseract-ocr` + pacotes de idioma (OCR local). Python: `pip install -e ".[dev]"`.
