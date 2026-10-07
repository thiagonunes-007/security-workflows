# CKB — Catholic Knowledge Base

Base de conhecimento curada que alimenta o assistente. **Qualidade e licença vêm antes de volume.**

## Estrutura
```
ckb/sources.yaml          registro de fontes (autoridade, idioma, status de licença)
ckb/corpus/<id>.jsonl     um arquivo por fonte; uma linha = um trecho citável
ckb/schema.py             modelos Source / Passage e carregadores
scripts/ckb_validate.py   valida registro + corpus (usar no CI)
scripts/ingest.py         envia ao índice vetorial; recusa fontes sem licença
```

## Trecho (Passage)
`{"source_id","ref","text","section","language"}` — `ref` é a citação exata e única na fonte
(`CIC §1213`, `Jo 3,16`, `ST I, q.1, a.1`). Um trecho = unidade natural, nunca corte arbitrário por tamanho.

## Níveis de autoridade
`escritura` > `magisterio` > `padres` > `teologo`. O nível aparece na resposta, para o usuário
distinguir doutrina definida de opinião teológica.

## Licença (`license_status`)
`livre` e `licenciado` podem ser ingeridos; `verificar` e `bloqueado` não. Mude o status só com
a evidência registrada em `license_note`.

## Como adicionar uma fonte
1. Registre em `sources.yaml` (status `verificar` até confirmar direitos).
2. Escreva um conversor `fonte → ckb/corpus/<id>.jsonl` preservando a numeração oficial.
3. `python -m scripts.ckb_validate` → `python -m scripts.ingest <id>`.
4. Amostre 30 trechos e peça revisão de um teólogo/catequista antes de publicar.

## Observações
- Bíblia católica precisa dos **deuterocanônicos**: a Almeida (protestante) está bloqueada.
- Muitas fontes livres estão em latim/inglês; o embedding multilíngue permite buscar em português,
  mas as citações exibidas devem ser traduzidas com cuidado (ou priorizar fontes em português licenciadas).

## Fontes prontas: Douay-Rheims (en) e Vulgata Clementina (la)
```bash
curl -sSLO https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/DRC.json
python -m scripts.convert_scrollmapper_bible douay_rheims DRC.json      # --window N agrupa N versículos
python -m scripts.ckb_validate && python -m scripts.ingest douay_rheims
```
Gera `corpus/douay_rheims.jsonl` (73 livros, refs como `Jo 3,16`) e `.provenance.json` (URL, sha256,
lacunas). Salmos usam a numeração da Vulgata. **12 versículos vêm vazios na fonte** (listados no
provenance); completar a partir de outra edição antes de publicar.

## Multilinguismo (9 idiomas)
`grc` grego · `hbo` hebraico · `la` latim · `pt` · `en` · `it` · `de` · `es` · `fr`
(códigos em `ckb/languages.py`; todo `Source.language` é validado contra essa lista).

**Alinhamento por `canon_ref`** — chave neutra de idioma (`John.3.16`, `CIC.1213`). A busca semântica
acha o trecho na língua mais próxima da pergunta; `rag.expand_aligned` anexa o mesmo trecho em
grego/hebraico/latim (`CONTEXT_LANGUAGES`) para o modelo citar o original e traduzir.

**Normalização para busca** — hebraico sem cantilação/niqqud, grego sem acentos/espíritos. O índice
usa o texto normalizado; o original fica em metadado e é o que se exibe.

**Armadilhas**
- Salmos: Vulgata/LXX × hebraica têm numeração diferente. `canon_ref` usa Vulgata; fontes
  `versification: hebraica` devem usar `ckb/psalms.py` (`hebrew_canon_refs`). Detalhes, nível de
  confiança e limites em `ckb/PSALMS.md`.
- Hebraico só cobre o protocanônico; deuterocanônicos vêm do grego/latim.
- Embeddings: latim, grego antigo e hebraico bíblico são mal cobertos por modelos pequenos. Em produção
  teste `BAAI/bge-m3` (100+ línguas) contra o conjunto de avaliação; o alinhamento por `canon_ref`
  reduz a dependência do embedding nessas línguas.
- Mensagem de "sem fundamento" ainda é só em português.

Cada fonte nova das línguas acima já está registrada em `sources.yaml` com status `verificar`.

**Vulgata Clementina (latim):** `python -m scripts.convert_scrollmapper_bible vulgata_clementina VulgClementine.json`
(arquivo `VulgClementine.json` do mesmo repositório). Mesmo formato e mesmo `canon_ref` da Douay-Rheims,
então os dois se alinham versículo a versículo. A Vulgata fica em `corpus/vulgata_clementina.jsonl`,
com 8 versículos vazios na fonte (listados no provenance). Na normalização de busca, as ligaduras
`æ`/`œ` viram `ae`/`oe`; o texto original é preservado.

## Hebraico (WLC/OSHB) alinhado à Vulgata
```bash
# baixe os 39 XML de https://github.com/openscriptures/morphhb/tree/master/wlc (ver docstring do script)
python -m scripts.convert_scrollmapper_bible vulgata_clementina VulgClementine.json   # pré-requisito
python -m scripts.convert_oshb_hebrew PASTA_COM_XML      # ~1 min; gera wlc_hebrew.jsonl (23.213 versículos)
```
`ref` usa a numeração **hebraica** (Sl 23,1); `canon_ref` aponta o versículo latino (Ps.22.1). O campo
`align` diz como o par foi obtido (confiança decrescente):

| `align` | Método | Confiança |
|---|---|---|
| `psalmos-exato` / `-verificado` / `-capitulo` | `ckb/psalms.py` (ver `PSALMS.md`) | alta / alta / média |
| `estrutural` | `ckb/books_map.py` (Ester, Daniel: acréscimos gregos) | alta (fronteiras conferidas no latim) |
| `identico` | alinhador por comprimento, mesmo cap./vers. | alta |
| `deslocado` | alinhador, numeração diferente (Jl 3,1 = Jl 2,28 etc.) | boa: pontos de controle conhecidos conferem |
| `incerto` | bead não 1:1 ou vizinho de um | **baixa** — o RAG sinaliza "alinhamento incerto" |
| *(vazio)* | sem par latino | — |

Dois versículos hebraicos podem cair no mesmo latino (Nm 25,19 e 26,1 = Nm 26,1) e um hebraico pode cobrir
dois latinos (`canon_ref_2`).

**Limites**
- O alinhador (`ckb/align.py`) é heurístico (comprimento dos versículos); concordou com a tabela dos Salmos
  em 99,6% (2.518/2.527). Foi conferido contra ~40 concordâncias conhecidas (Jl, Ml, Nm 17, Dt 13, Jó 41,
  Os 2, Mq 4–5, Zc 2, Ne 3–4/10, 1–2Sm, 1–2Rs…), mas **não houve revisão verso a verso**.
- `canon_ref` dos livros que não são Salmos segue a numeração do dataset latino usado (scrollmapper), que
  em alguns livros coincide com a hebraica (ex.: Jonas 2,1). Isso é consistente com a Douay-Rheims (35.800
  de 35.805 refs em comum), mas pode diferir da numeração impressa da Clementina.
- Ketiv é mantido no corpo; qere e variantes (`<note>`) são descartados. Texto com cantilação e vocalização
  originais; a busca usa a versão normalizada (`normalize_for_search`).
- Sem deuterocanônicos (não existem no WLC); no hebraico, esses livros vêm do grego/latim.
