#!/usr/bin/env bash
set -euo pipefail

# Somente demonstração no Render Free: nada aqui é persistente.
: "${CT_DEMO_PASSWORD:?Configure CT_DEMO_PASSWORD em Environment com uma senha exclusiva de no mínimo 12 caracteres.}"
if (( ${#CT_DEMO_PASSWORD} < 12 )); then
  echo "CT_DEMO_PASSWORD deve ter no mínimo 12 caracteres." >&2
  exit 1
fi
if [[ "${CT_SECURE_COOKIE:-0}" != "1" ]]; then
  echo "Configure CT_SECURE_COOKIE=1 para acesso via HTTPS." >&2
  exit 1
fi

# Cadastro público somente para o ambiente de demonstração.
export CT_ALLOW_SIGNUP=1
# Habilita somente a escolha simulada Pix/boleto/cartão (sem cobranças reais).
export CT_PAYMENT_DEMO=1

# Caminho propositalmente temporário: nunca use dados reais neste serviço.
export CT_DB=/tmp/ctpulse-demo.sqlite3

# Reinicia sempre com dados sintéticos. Cuidado: isso apaga alterações da demo.
rm -f -- "${CT_DB}" "${CT_DB}-wal" "${CT_DB}-shm"
python server.py demo

# Uma única instância Gunicorn adequada à demonstração com recursos limitados.
exec gunicorn --bind "0.0.0.0:${PORT:-10000}" --workers 1 --threads 2 --timeout 90 server:app
