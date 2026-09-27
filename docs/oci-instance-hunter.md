# OCI Free-Tier Instance Hunter

Workflow que fica tentando criar uma instancia do plano **Always Free** da
Oracle Cloud ate conseguir, contornando o erro **`Out of host capacity`** —
aquele que sempre aparece quando voce tenta criar a maquina ARM
(`VM.Standard.A1.Flex`) pelo console.

Como funciona: um job agendado (cron, a cada 15 min) tenta lancar a
instancia em todos os *availability domains* da sua regiao. Se nao houver
capacidade, ele nao falha — so espera o proximo agendamento e tenta de
novo. Assim que a Oracle liberar capacidade, a instancia e criada e o
workflow passa a detectar que ela ja existe (e para de tentar).

## 1. Pre-requisitos na Oracle Cloud

1. **Uma rede (VCN) com subnet publica.** No console OCI:
   *Networking -> Virtual Cloud Networks -> Start VCN Wizard ->
   "Create VCN with Internet Connectivity"*. Isso cria a VCN, o internet
   gateway e uma **subnet publica**. Guarde o **OCID da subnet publica**.

2. **Uma chave de API.** No console: clique no seu avatar (canto superior
   direito) -> *User settings -> API keys -> Add API Key -> Generate API
   Key Pair*. Baixe a **private key** (`.pem`). A tela mostra um bloco de
   configuracao com `user`, `fingerprint`, `tenancy` e `region` — anote.

3. **Um par de chaves SSH** pra acessar a maquina depois
   (`ssh-keygen -t ed25519`). Voce vai usar a **chave publica**.

## 2. Secrets no GitHub

No repo: **Settings -> Secrets and variables -> Actions -> aba _Secrets_ ->
New repository secret**. Crie:

| Secret | O que e / onde achar |
|---|---|
| `OCI_CLI_USER` | OCID do seu usuario (User settings -> OCID, ou no bloco de config da API key) |
| `OCI_CLI_TENANCY` | OCID da tenancy (mesmo bloco de config) |
| `OCI_CLI_FINGERPRINT` | Fingerprint da chave de API (mostrado ao criar a chave) |
| `OCI_CLI_KEY_CONTENT` | **Conteudo inteiro** do arquivo `.pem` da private key (cole tudo, incluindo as linhas `-----BEGIN/END-----`) |
| `OCI_CLI_REGION` | Regiao, ex.: `sa-saopaulo-1`, `sa-vinhedo-1`, `us-ashburn-1` |
| `OCI_COMPARTMENT_ID` | OCID do compartment onde criar a instancia. Pode ser a **tenancy root** (mesmo valor de `OCI_CLI_TENANCY`) |
| `OCI_SUBNET_ID` | OCID da **subnet publica** criada no passo 1 |
| `OCI_SSH_AUTHORIZED_KEYS` | Sua **chave publica** SSH (conteudo do `.pub`, uma linha) |

> A `OCI_CLI_REGION` precisa ser a **home region** da subnet — a instancia
> e criada na regiao da subnet informada.

## 3. Variables opcionais

Aba **_Variables_** (mesma tela). Todas tem default, entao so mexa se
quiser trocar:

| Variable | Default | Descricao |
|---|---|---|
| `OCI_DISPLAY_NAME` | `free-arm-hunter` | Nome da instancia (usado tambem pra detectar se ja existe) |
| `OCI_OS` | `Canonical Ubuntu` | Sistema operacional da imagem |
| `OCI_OS_VERSION` | `22.04` | Versao do SO |

## 4. Rodando

- **Teste manual primeiro:** aba *Actions -> OCI Free-Tier Instance Hunter
  -> Run workflow*. Da pra ajustar `shape`, `ocpus` e `memory_gb` na hora.
  Isso valida suas credenciais na hora (o passo "Configura credenciais"
  falha rapido com mensagem clara se algo estiver errado).
- **Deixe o cron rodando:** ele tenta a cada ~15 min sozinho. O GitHub pode
  atrasar ou pular runs agendadas sob carga — e normal.
- **Quando conseguir:** o resumo da run mostra o **OCID** e o **IP publico**.
  Conecte com `ssh ubuntu@<IP>` (usuario `ubuntu` nas imagens Canonical;
  `opc` nas imagens Oracle Linux). Depois **desabilite o cron** (Actions ->
  o workflow -> `...` -> Disable workflow) pra parar de tentar.

## Interpretando os resultados

| Resultado da run | Significado |
|---|---|
| :white_check_mark: verde, com OCID/IP no resumo | Instancia criada. |
| :white_check_mark: verde, "Sem instancia nesta rodada" | Sem capacidade agora (`Out of host capacity`) ou ja existe uma instancia. Normal — vai tentar de novo. |
| :x: vermelho no passo "Configura credenciais" | Secret errado/faltando (auth). Confira `OCI_CLI_*`. |
| :x: vermelho no passo "Caca instancia" | Erro real de config (subnet/compartment/imagem invalidos, ou limite always-free ja atingido em outro formato). Veja o log. |

## Dica: E2.1.Micro (AMD) costuma ter capacidade

Se o ARM `A1.Flex` estiver impossivel na sua regiao, o shape AMD
`VM.Standard.E2.1.Micro` (1 OCPU / 1 GB, tambem always-free) quase sempre
tem capacidade. Rode manualmente com:

- `shape` = `VM.Standard.E2.1.Micro`

(ocpus/memory sao ignorados nesse shape, que e fixo.)
