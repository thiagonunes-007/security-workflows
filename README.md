# security-workflows

Workflow reutilizavel de pentest automatico com [Strix](https://strix.ai)
(CLI self-hosted, roda dentro do proprio GitHub Actions do repositorio
chamador) para ser usado como padrao em todos os repositorios pessoais.

Fonte unica de verdade: quando a logica do scan mudar (nova flag, novo
guard, etc.), atualiza aqui uma vez e todo repo que aponta pra esse
workflow pega a versao nova automaticamente na proxima run.

## Como adicionar num repositorio novo

1. Cria `.github/workflows/security.yml` no repo com:

```yaml
name: Security Scan

on:
  pull_request:

jobs:
  strix-scan:
    permissions:
      contents: read
      security-events: write
      actions: read
    uses: thiagonunes-007/security-workflows/.github/workflows/strix-scan.yml@main
    secrets: inherit
```

> `security-events: write` e `actions: read` sao obrigatorios aqui —
> um workflow reutilizavel nunca recebe mais permissao do que o
> chamador concede, entao sem isso o upload do SARIF falha mesmo que
> o scan em si complete normalmente.

2. No repo, em **Settings -> Secrets and variables -> Actions**, adiciona:
   - `STRIX_LLM` - id do modelo (ex.: `anthropic/claude-sonnet-5`)
   - `LLM_API_KEY` - chave da API desse provedor

Pronto. Todo PR passa a ser escaneado automaticamente, escopado ao
diff, e a build falha se o Strix encontrar vulnerabilidade validada.

## Scan completo agendado (opcional, recomendado antes de release)

Alem do scan por PR (rapido, so o diff), da pra rodar um scan `standard`
ou `deep` do repo inteiro numa cadencia fixa - por exemplo, toda
segunda de madrugada, ou antes de marcar uma tag de release:

```yaml
name: Security Scan (full, agendado)

on:
  schedule:
    - cron: "0 6 * * 1" # toda segunda, 06:00 UTC
  workflow_dispatch: {} # tambem permite rodar manualmente

jobs:
  strix-scan-full:
    permissions:
      contents: read
      security-events: write
      actions: read
    uses: thiagonunes-007/security-workflows/.github/workflows/strix-scan.yml@main
    with:
      scope-mode: full
      scan-mode: standard
      max-budget: 30
    secrets: inherit
```

## Inputs disponiveis

| Input | Default | Descricao |
|---|---|---|
| `target` | `./` | Diretorio/alvo do scan |
| `scan-mode` | `quick` | `quick` \| `standard` \| `deep` |
| `max-budget` | `10` | Orcamento maximo (USD) da run |
| `scope-mode` | `diff` | `diff` (so o PR) ou `full` (repo inteiro) |

## Repos que ja usam este workflow

- [MedDecision](https://github.com/thiagonunes-007/MedDecision) (saude-app)
- [MedDecision-ckb](https://github.com/thiagonunes-007/MedDecision-ckb)
- [meddecision-oci-instance-hunter](https://github.com/thiagonunes-007/meddecision-oci-instance-hunter)
