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
