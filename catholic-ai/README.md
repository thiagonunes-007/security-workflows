# Catholic AI — assistente católico via WhatsApp

Assistente de estudo da fé que responde **somente com base em fontes citáveis**
(Escritura, Tradição, Magistério), entregue pelo WhatsApp (MVP mobile, sem app próprio).

## Fluxo
```
WhatsApp → Meta Cloud API → POST /webhook (FastAPI, assinatura HMAC validada)
  → busca vetorial (Chroma + embeddings multilíngues) nas fontes
  → sem trechos relevantes? resposta de "sem fundamento" (LLM nem é chamado)
  → Claude responde só com os trechos e cita [CIC §…, Jo 3,16]
  → resposta enviada ao usuário (dividida se > 4096 caracteres)
```

## Rodando local
```bash
cd catholic-ai
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # preencha as chaves
python -m scripts.ckb_validate
python -m scripts.ingest douay_rheims
uvicorn app.main:app --reload
pytest
```
Para testar o webhook, exponha a porta (ngrok/cloudflared) e configure a URL
`/webhook` + `WHATSAPP_VERIFY_TOKEN` no painel Meta for Developers (WhatsApp → Configuration).

## Formato do corpus (JSONL)
Corpus em `ckb/corpus/<source_id>.jsonl`, fontes em `ckb/sources.yaml`.
Ver `ckb/README.md`.

## Decisões de design
- **Fundamentação acima de fluência**: relevância mínima (`MIN_SCORE`) e prompt que proíbe citar além das fontes.
- **Hierarquia de autoridade** nos metadados e no prompt.
- **Não é sacerdote**: sem confissão/direção espiritual; encaminha casos pessoais e crises.
- **LGPD**: número de telefone só é guardado como hash; histórico curto, em memória.
- **Segurança**: assinatura `X-Hub-Signature-256`, deduplicação de eventos, rate limit por usuário.

## Pendências antes de ir a público
1. **Direitos autorais**: licenças do CIC (LEV), traduções bíblicas e documentos do Vaticano.
2. **Corpus**: ingestores para CIC, Vaticano II, encíclicas, CDC, Padres, Suma (parsing + chunking por unidade).
3. **Avaliação**: 100–300 perguntas validadas por teólogo; testes de alucinação de citação.
4. **Estado persistente** (Redis/Postgres) para histórico, rate limit e dedup em múltiplas instâncias.
5. **Revisão eclesial**: supervisão de um clérigo/teólogo; considerar nihil obstat conforme o caso.
6. **WhatsApp Business**: verificação da conta e política de mensagens da Meta.
7. App nativo (Flutter/React Native) só depois de validar o canal WhatsApp.
