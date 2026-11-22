#!/usr/bin/env bash
set -euo pipefail

# Demonstração acadêmica com estado remoto no Firestore; não usar com dados reais.
: "${CT_DEMO_PASSWORD:?Defina CT_DEMO_PASSWORD no Render (12 ou mais caracteres)}"
if (( ${#CT_DEMO_PASSWORD} < 12 )); then
  echo "CT_DEMO_PASSWORD deve ter ao menos 12 caracteres." >&2
  exit 1
fi
if [[ "${CT_SECURE_COOKIE:-0}" != "1" ]]; then
  echo "Defina CT_SECURE_COOKIE=1 para acesso via HTTPS." >&2
  exit 1
fi
: "${FIREBASE_PROJECT_ID:?Configure FIREBASE_PROJECT_ID=ct-pulse}"
if [[ "${FIREBASE_PROJECT_ID}" != "ct-pulse" ]]; then
  echo "FIREBASE_PROJECT_ID diferente do projeto esperado." >&2
  exit 1
fi
: "${FIREBASE_SERVICE_ACCOUNT_JSON:?Configure a credencial JSON como segredo no Render}"

# Não apaga nem recria arquivos de banco em cada deploy.
export CT_PERSISTENCE=firestore
export CT_FIRESTORE_DEMO_SEED=1
export CT_ALLOW_SIGNUP=1
export CT_PAYMENT_DEMO=1

# Valida conexão sem exibir credenciais e falha de forma segura.
python firebase_store.py
exec gunicorn --bind "0.0.0.0:${PORT:-10000}" --workers 1 --threads 2 --timeout 90 server:app
