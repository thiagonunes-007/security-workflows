---
title: Catholic AI — síntese do desenvolvimento
type: project-synthesis
project: catholic-ai
status: em andamento (corpus multilíngue pronto; avaliação e pt/it/es pendentes)
created: 2026-10-07
updated: 2026-10-08
tags: [catholic-ai, rag, whatsapp, ckb, multilingual, bible, licensing]
repo: thiagonunes-007/security-workflows (pasta catholic-ai/, branch ccr-d375248b-2gaq45)
---

# Catholic AI — síntese do desenvolvimento

## Objetivo
Um assistente "tipo Claude, mas católico": responde **somente com base em fontes citáveis** ([[Escritura]],
[[Tradição]], [[Magistério]]), em português por padrão, entregue pelo [[WhatsApp]] (MVP mobile, sem app próprio).
Não simula sacerdote, confissão nem direção espiritual. Python.

## Decisão de arquitetura
Não treinar modelo. Usar [[RAG]] sobre um acervo curado + [[Claude]] + prompt rígido de fundamentação.

```
WhatsApp → Meta Cloud API → POST /webhook (FastAPI, HMAC)
  → busca vetorial (Chroma, embeddings multilíngues) no [[CKB]]
  → sem trecho relevante: "sem fundamento" (LLM nem é chamado)
  → Claude responde só com os trechos, citando; anexa o mesmo trecho em grego/hebraico/latim via [[canon_ref]]
```

## Linha do tempo
1. **Fundação** — esqueleto FastAPI + RAG + WhatsApp (assinatura HMAC, dedup, rate limit, hash do telefone/LGPD).
2. **[[CKB]]** — registro de fontes com status de licença; ingestão bloqueia fontes sem licença.
3. **Bíblias** — Douay-Rheims (en) e Vulgata Clementina (la), 73 livros, versículo a versículo, com `canon_ref`.
4. **Multilinguismo (9 idiomas)** — grc, hbo, la, pt, en, it, de, es, fr; normalização para busca (hebraico sem
   niqqud, grego sem acentos, latim æ→ae); alinhamento entre línguas por `canon_ref`.
5. **[[Salmos]]** — mapa hebraico↔Vulgata (150 salmos), auditado contra o hebraico (OSHB).
6. **Hebraico** — Westminster Leningrad Codex (39 livros) alinhado à Vulgata.
7. **Completar línguas** — grego NT (Byzantine) e AT ([[Swete]]/LXX), alemão ([[Allioli]]), francês (Giguet).
8. **Pipeline de documentos** — PDF/OCR/DOCX/EPUB → limpeza → segmentação → Bíblias digitalizadas (pt/it/es).
9. **Transferência** — `CLAUDE.md` no repositório para continuar no VS Code.

## Estado do corpus
| Idioma | source_id | Cobertura | Alinhado à Vulgata | Licença |
|---|---|---|---|---|
| la | vulgata_clementina | 73 livros, 35.809 v. | referência | domínio público |
| en | douay_rheims | 73 livros, 35.805 v. | 35.800 | domínio público |
| hbo | wlc_hebrew | 39 livros, 23.213 v. | ~23.000 | domínio público |
| grc NT | byz_nt | 27 livros, 7.953 v. | 7.618 | domínio público |
| grc AT | lxx_swete | 45 livros, 26.853 v. | 19.008 | **CC BY-SA 4.0** (mantido por decisão do usuário) |
| de | allioli_de | 68/73 livros, 33.115 v. | ~33.100 | domínio público (idade) |
| fr | fr_lxx_giguet | só AT, 27.112 v. | ~20.000 | domínio público (idade) |
| pt · it · es | — | **sem corpus** | — | ver [[Pendências]] |

## Conceitos-chave
- **canon_ref** — chave neutra de idioma (`John.3.16`, `Ps.22.1`) na numeração da Vulgata; `canon_ref_2` quando um
  versículo cobre dois; campo `align` registra *como* o par foi obtido.
- **Alinhamento em camadas** — Salmos por tabela; Ester/Daniel por regra estrutural; demais por programação
  dinâmica de comprimento ([[Gale-Church]] simplificado) + **auditoria independente por nomes próprios**.
- **Trava de licença** — só `livre|licenciado` com evidência vai para `ckb/corpus/`; o resto fica em
  `ckb/staging/` (ignorado pelo git).

## Achados e lições (o que deu errado e como foi corrigido)
- **Ester e Daniel saíram errados** no alinhador por comprimento (acréscimos gregos). Rotular como "incerto" não
  bastava → regra estrutural conferida contra o texto latino.
- **Contagem de versículos não basta** (Sl 12 tinha a mesma contagem, mas deslocado) → leitura lado a lado.
- **A trava de qualidade de 40% era branda** para a LXX: Jeremias, Jó, Judite, Neemias passavam com pares errados
  → criada auditoria por nomes próprios (`ckb/verify.py`); linha de base no NT = 85%; abaixo de 65% o par perde o
  `canon_ref` (o texto permanece). Resultado: 18.446 pares `identico` verificados na LXX; 7.845 versículos sem par.
- **Numeração dos Salmos** — 4 casos estruturais (9–10, 114–115, 116, 147) exatos; 6 salmos verificados por leitura
  (2, 4, 10, 12, 43, 55); demais assumidos idênticos após teste de deslocamento (5 falsos positivos lidos).
- **Textos que pareciam livres não eram**: Crampon 1923, Platense e as traduções atuais (Ave Maria, CNBB, CEI,
  Bíblia de Jerusalém) têm direitos incertos/reservados → fora do corpus.
- Bíblias protestantes (Almeida, Reina-Valera) **não incluídas**: sem deuterocanônicos e leituras doutrinárias
  diferentes (ex.: Lc 1,28).
- O Allioli do GitHub cobre 68/73 livros (faltam 1–2 Reis, Esdras, Romanos, Hebreus) e o latim do TSV perdeu ligaduras.
- Erros meus de processo também foram corrigidos: commit com teste falhando, `__pycache__` versionado.

## Pipeline de documentos (`ckb/PIPELINE.md`)
`scan → catalog.local.yaml (você revisa) → run → ckb/staging/ → promote → ckb/corpus/`
- Extração: PDF (camada de texto; OCR por página via `tesseract` ou visão do Claude), DOCX, EPUB, HTML, ODT/RTF.
- Segmentação: `numbered` (CIC/encíclicas), `prose`, `bible` (acha livros/capítulos/versículos guiado pela
  sequência; alinha à Vulgata; mede cobertura de versículos por capítulo — alvo ≥ 97%).
- `promote` exige `license_status` livre/licenciado **e** `license_evidence`.

## Pendências (ordem sugerida)
1. **pt/it/es**: rodar o pipeline na pasta `igreja` (no notebook do usuário) e trazer catálogo + `*.provenance.json`.
   Candidatos de domínio público: Figueiredo (pt), Martini (it), Torres Amat/Scío (es) — só existem como scans.
2. **Conjunto de avaliação** (100–300 perguntas validadas por teólogo) — decide embeddings (testar `bge-m3`) e janela.
3. Licenciar CIC, Vaticano II, CDC e traduções atuais (LEV, CNBB, Ave-Maria, CEI).
4. Estado persistente (Redis/Postgres), mensagem "sem fundamento" multilíngue, revisão de teólogo, WhatsApp Business.
5. Mover `catholic-ai/` para repositório próprio.

## Não verificado (não tratar como feito)
`scripts.ingest` com embeddings reais · OCR real (só simulado) · revisão verso a verso do alinhamento hebraico/grego ·
fidelidade dos textos contra edições impressas.

## Números
52 testes passando · ~58 MB de corpus · 7 fontes convertidas · 17 fontes ainda `verificar` no registro.

## Mapa de arquivos
[[CLAUDE.md]] (contexto para o Claude Code) · `ckb/README.md` · `ckb/PSALMS.md` · `ckb/PIPELINE.md` ·
`ckb/sources.yaml` · `scripts/` (conversores, `ckb_validate`, `ingest`, `audit_alignment`, `docs_pipeline`) · `tests/`.
