#!/usr/bin/env bash
#
# oci-hunter.sh - caca uma instancia free-tier da Oracle Cloud (OCI).
#
# O problema classico do plano "Always Free" (principalmente do shape ARM
# VM.Standard.A1.Flex) e o erro "Out of host capacity": a Oracle recusa a
# criacao porque nao ha capacidade no availability domain naquele momento.
# A unica solucao real e tentar de novo, repetidamente, ate a capacidade
# aparecer. Este script faz uma rodada de tentativa; o cron do workflow
# repete a rodada de tempos em tempos.
#
# Comportamento por tipo de resultado:
#   - Instancia criada          -> sucesso (exit 0), imprime OCID + IP publico
#   - Ja existe instancia        -> sucesso (exit 0), nao faz nada (para de martelar)
#   - "Out of host capacity"     -> exit 0 "soft": sem capacidade agora, o cron
#                                    tenta de novo. NAO falha a run (evita spam
#                                    de e-mail de falha do GitHub a cada 15 min).
#   - Limite always-free atingido-> exit 0 "soft": voce ja tem o maximo permitido.
#   - Erro real (auth/config)    -> exit 1: falha a run pra voce ver e corrigir.
#
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuracao (via env; defaults miram o ARM free-tier A1.Flex completo).
# ---------------------------------------------------------------------------
: "${OCI_COMPARTMENT_ID:?defina OCI_COMPARTMENT_ID (OCID do compartment, normalmente = tenancy)}"
: "${OCI_SUBNET_ID:?defina OCI_SUBNET_ID (OCID da subnet publica onde a instancia entra)}"
: "${OCI_SSH_AUTHORIZED_KEYS:?defina OCI_SSH_AUTHORIZED_KEYS (sua chave publica SSH)}"

SHAPE="${OCI_SHAPE:-VM.Standard.A1.Flex}"
OCPUS="${OCI_OCPUS:-4}"
MEMORY_GB="${OCI_MEMORY_GB:-24}"
BOOT_GB="${OCI_BOOT_VOLUME_GB:-50}"
DISPLAY_NAME="${OCI_DISPLAY_NAME:-free-arm-hunter}"
OS_NAME="${OCI_OS:-Canonical Ubuntu}"
OS_VERSION="${OCI_OS_VERSION:-22.04}"
ASSIGN_PUBLIC_IP="${OCI_ASSIGN_PUBLIC_IP:-true}"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

log()  { printf '%s %s\n' "$(date -u +%H:%M:%S)" "$*"; }
soft_stop() { log "SOFT-STOP: $*"; exit 0; }

# ---------------------------------------------------------------------------
# 1. Ja existe uma instancia nossa? Se sim, nao faz nada.
#    Para de martelar a API depois que conseguimos a maquina.
# ---------------------------------------------------------------------------
log "Verificando se ja existe instancia '$DISPLAY_NAME'..."
existing="$(oci compute instance list \
  --compartment-id "$OCI_COMPARTMENT_ID" \
  --all \
  --query "data[?\"display-name\"=='$DISPLAY_NAME' && (\"lifecycle-state\"=='RUNNING' || \"lifecycle-state\"=='PROVISIONING' || \"lifecycle-state\"=='STARTING')].id | [0]" \
  --raw-output 2>/dev/null || true)"

if [[ -n "$existing" && "$existing" != "null" ]]; then
  soft_stop "instancia ja existe ($existing). Nada a fazer."
fi

# ---------------------------------------------------------------------------
# 2. Resolve a imagem mais recente para o SO/shape (evita OCID hardcoded).
# ---------------------------------------------------------------------------
log "Resolvendo imagem para '$OS_NAME $OS_VERSION' no shape '$SHAPE'..."
IMAGE_ID="$(oci compute image list \
  --compartment-id "$OCI_COMPARTMENT_ID" \
  --operating-system "$OS_NAME" \
  --operating-system-version "$OS_VERSION" \
  --shape "$SHAPE" \
  --sort-by TIMECREATED --sort-order DESC \
  --query 'data[0].id' --raw-output 2>/dev/null || true)"

if [[ -z "$IMAGE_ID" || "$IMAGE_ID" == "null" ]]; then
  log "ERRO: nao encontrei imagem para '$OS_NAME $OS_VERSION' compativel com '$SHAPE'."
  log "Verifique OCI_OS / OCI_OS_VERSION / OCI_SHAPE e as permissoes do compartment."
  exit 1
fi
log "Imagem: $IMAGE_ID"

# ---------------------------------------------------------------------------
# 3. Metadata (chave SSH) e shape-config.
# ---------------------------------------------------------------------------
python3 - "$OCI_SSH_AUTHORIZED_KEYS" > "$WORKDIR/metadata.json" <<'PY'
import json, sys
print(json.dumps({"ssh_authorized_keys": sys.argv[1]}))
PY

shape_config_args=()
# Shapes .Flex precisam de --shape-config; shapes fixos (ex.: E2.1.Micro) nao.
if [[ "$SHAPE" == *".Flex" ]]; then
  printf '{"ocpus": %s, "memoryInGBs": %s}' "$OCPUS" "$MEMORY_GB" > "$WORKDIR/shape_config.json"
  shape_config_args=(--shape-config "file://$WORKDIR/shape_config.json")
fi

# ---------------------------------------------------------------------------
# 4. Descobre os availability domains e tenta em cada um.
#    A capacidade varia por AD, entao vale tentar todos.
# ---------------------------------------------------------------------------
mapfile -t ADS < <(oci iam availability-domain list \
  --compartment-id "$OCI_COMPARTMENT_ID" 2>/dev/null \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); [print(a["name"]) for a in d.get("data",[])]' 2>/dev/null || true)

if [[ "${#ADS[@]}" -eq 0 ]]; then
  log "ERRO: nao consegui listar availability domains (auth/permissao?)."
  exit 1
fi
log "Availability domains: ${ADS[*]}"

capacity_hit=0
limit_hit=0

for AD in "${ADS[@]}"; do
  log "Tentando lancar em AD: $AD ..."
  err_file="$WORKDIR/err.txt"
  out_file="$WORKDIR/out.json"

  if oci compute instance launch \
      --availability-domain "$AD" \
      --compartment-id "$OCI_COMPARTMENT_ID" \
      --shape "$SHAPE" \
      "${shape_config_args[@]}" \
      --image-id "$IMAGE_ID" \
      --subnet-id "$OCI_SUBNET_ID" \
      --assign-public-ip "$ASSIGN_PUBLIC_IP" \
      --boot-volume-size-in-gbs "$BOOT_GB" \
      --metadata "file://$WORKDIR/metadata.json" \
      --display-name "$DISPLAY_NAME" \
      > "$out_file" 2> "$err_file"; then

    INSTANCE_ID="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["data"]["id"])' "$out_file")"
    log "SUCESSO! Instancia criada: $INSTANCE_ID (AD: $AD)"

    # Espera ficar RUNNING e pega o IP publico.
    log "Aguardando estado RUNNING..."
    for _ in $(seq 1 30); do
      state="$(oci compute instance get --instance-id "$INSTANCE_ID" --query 'data."lifecycle-state"' --raw-output 2>/dev/null || echo '')"
      [[ "$state" == "RUNNING" ]] && break
      sleep 10
    done

    PUB_IP="$(oci compute instance list-vnics --instance-id "$INSTANCE_ID" \
      --query 'data[0]."public-ip"' --raw-output 2>/dev/null || echo 'pendente')"

    {
      echo "instance_id=$INSTANCE_ID"
      echo "availability_domain=$AD"
      echo "public_ip=$PUB_IP"
    } >> "${GITHUB_OUTPUT:-/dev/null}"

    log "=============================================="
    log " Instancia: $INSTANCE_ID"
    log " IP publico: $PUB_IP"
    log " SSH: ssh ubuntu@$PUB_IP   (usuario 'ubuntu' p/ imagens Canonical)"
    log "=============================================="
    exit 0
  fi

  err="$(cat "$err_file")"
  log "Falha no AD $AD:"
  echo "$err" | sed 's/^/    /'

  # Classifica o erro.
  if grep -qiE 'out of (host )?capacity|internalerror.*capacity|500.*capacity' <<<"$err"; then
    capacity_hit=1
    log " -> sem capacidade neste AD, tento o proximo."
    continue
  fi
  if grep -qiE 'limitexceeded|limit exceeded|quota|already .* maximum' <<<"$err"; then
    limit_hit=1
    log " -> parece limite de conta atingido."
    continue
  fi

  # Erro nao reconhecido = provavelmente config/auth. Falha pra ser visto.
  log "ERRO nao relacionado a capacidade. Abortando pra voce corrigir."
  exit 1
done

if [[ "$limit_hit" -eq 1 ]]; then
  soft_stop "limite de recursos always-free atingido (voce provavelmente ja tem o maximo). Nada a tentar."
fi

if [[ "$capacity_hit" -eq 1 ]]; then
  soft_stop "sem capacidade em nenhum AD agora ('Out of host capacity'). O cron tenta de novo depois."
fi

soft_stop "nenhuma tentativa teve sucesso, mas sem erro fatal. Repito no proximo agendamento."
