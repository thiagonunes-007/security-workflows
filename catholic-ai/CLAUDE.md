# Catholic AI — contexto do projeto

Assistente católico (estilo Claude) que responde **só com base em fontes citáveis** (Escritura, Tradição,
Magistério), entregue pelo **WhatsApp** (MVP mobile, sem app próprio). Python. O usuário fala português (pt-BR):
responda em português.

> Hoje vive na subpasta `catholic-ai/` do repositório `security-workflows` (que é de workflows de segurança).
> O ideal é mover para um repositório próprio.

## Arquitetura
```
WhatsApp → Meta Cloud API → POST /webhook (FastAPI, HMAC X-Hub-Signature-256)
  → busca vetorial (Chroma + embeddings multilíngues) no CKB
  → sem trecho relevante: resposta "sem fundamento" (o LLM nem é chamado)
  → Claude responde só com os trechos, citando; anexa o mesmo trecho em grego/hebraico/latim via canon_ref
```
- `app/` — API (`main.py`), RAG (`rag.py`), WhatsApp (`whatsapp.py`), prompts (`prompts.py`), config.
- `ckb/` — Catholic Knowledge Base: `sources.yaml` (registro + licença), `schema.py`, `languages.py`,
  `align.py`, `verify.py`, `psalms.py`, `books_map.py`, `docs/` (extração/limpeza/segmentação/Bíblias em OCR),
  `corpus/*.jsonl` (+ `.provenance.json`), docs: `README.md`, `PSALMS.md`, `PIPELINE.md`.
- `scripts/` — conversores (`convert_*`), `ckb_validate`, `ingest`, `audit_alignment`, `psalms_audit`, `docs_pipeline`.
- Testes: `python -m pytest -q tests` (52 passam). Validação do corpus: `python -m scripts.ckb_validate`.

## Conceitos-chave
- **canon_ref**: chave neutra de idioma que alinha o mesmo trecho entre línguas (`John.3.16`, `Ps.22.1`),
  na numeração da **Vulgata** (do dataset latino). `canon_ref_2` quando 1 versículo cobre 2. Campo `align`
  diz como o par foi obtido (identico | deslocado | incerto | estrutural | psalmos-*).
- **Alinhamento**: Salmos por tabela (`psalms.py`, ver `PSALMS.md`); Ester/Daniel por regra (`books_map.py`);
  demais por DP de comprimento (`align.py`) + **auditoria independente por nomes próprios** (`verify.py`,
  piso ~85% no NT). Pares não sustentados perdem o canon_ref; o texto permanece.
- **Licença**: só `livre|licenciado` entra em `ckb/corpus/`; o resto vai para `ckb/staging/` (gitignored).

## Estado do corpus
| Idioma | source_id | Cobertura |
|---|---|---|
| la | vulgata_clementina | 73 livros (referência) |
| en | douay_rheims | 73 livros |
| hbo | wlc_hebrew | 39 livros, alinhado |
| grc NT | byz_nt | 27 livros (texto bizantino, não NA/UBS) |
| grc AT | lxx_swete | 45 livros; sem Eclesiastes; Jó/Jdt/Pr/Sb/Lm/Tb/Est/Sir sem alinhamento — **CC BY-SA 4.0** |
| de | allioli_de | 68/73 (faltam 1-2Rs, Esd, Rm, Hb) |
| fr | fr_lxx_giguet | só AT |
| pt, it, es | — | **sem corpus** |

## Decisões já tomadas (não reabrir sem o usuário)
- **Manter o Swete** (CC BY-SA 4.0; atribuição em `ckb/corpus/lxx_swete.LICENSE.md`).
- **Não** incluir traduções protestantes (Almeida, Reina-Valera) por padrão: sem deuterocanônicos e leituras
  doutrinárias distintas (ex.: Lc 1,28).
- **Não** incluir Crampon 1923 nem Platense (direitos incertos). Pipeline do Crampon existe no scrollmapper.
- Nunca trocar `license_status` sem evidência escrita em `license_note`/`license_evidence`.
- Nunca commitar texto com direitos reservados.
- A IA **não** simula sacerdote, confissão ou direção espiritual (ver `app/prompts.py`).

## Pendências (ordem sugerida)
1. **Pt/it/es**: o usuário tem documentos no notebook (pasta `igreja`). Rodar `scripts/docs_pipeline` lá
   (`scan` → revisar catálogo → `run`) e trazer os `*.provenance.json`/catálogo para ajustar heurísticas.
   Candidatos de domínio público: Figueiredo (pt), Martini (it), Torres Amat/Scío (es) — só existem como scans.
2. **Conjunto de avaliação** (100–300 perguntas validadas por teólogo): ainda não existe; é ele que deve decidir
   o modelo de embeddings (testar `BAAI/bge-m3`) e `--window` dos versículos.
3. Mensagem "sem fundamento" ainda só em português.
4. Estado persistente (histórico, rate limit, dedup) em Redis/Postgres; hoje em memória.
5. Contato com LEV/CNBB/Ave-Maria/CEI para licenciar CIC, Vaticano II, CDC e traduções atuais.
6. Revisão de teólogo; verificação da conta WhatsApp Business (Meta).

## Não verificado (não afirme como feito)
- `scripts.ingest` com o modelo de embeddings real (download pode ser bloqueado em ambiente restrito).
- OCR real (`tesseract`/`claude`): testado só com simulações; sem PDF escaneado de verdade.
- Revisão verso a verso do alinhamento hebraico/grego (só amostras e auditoria automática).
- Fidelidade do latim/inglês/hebraico/alemão contra edições impressas.

## Dica de ambiente
Rede restrita na sessão web: `raw.githubusercontent.com` e PyPI funcionam; archive.org, gutenberg.org e
github.com (HTML) não. No notebook isso não se aplica.
