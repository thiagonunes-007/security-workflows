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

## Fonte pronta: Douay-Rheims (Challoner)
```bash
curl -sSLO https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/DRC.json
python -m scripts.convert_douay_rheims DRC.json      # --window N agrupa N versículos
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
  `versification: hebraica` precisam de mapeamento no conversor (ainda não implementado).
- Hebraico só cobre o protocanônico; deuterocanônicos vêm do grego/latim.
- Embeddings: latim, grego antigo e hebraico bíblico são mal cobertos por modelos pequenos. Em produção
  teste `BAAI/bge-m3` (100+ línguas) contra o conjunto de avaliação; o alinhamento por `canon_ref`
  reduz a dependência do embedding nessas línguas.
- Mensagem de "sem fundamento" ainda é só em português.

Cada fonte nova das línguas acima já está registrada em `sources.yaml` com status `verificar`.
