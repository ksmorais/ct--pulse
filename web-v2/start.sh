#!/usr/bin/env bash
set -euo pipefail

# Não iniciar a aplicação pública com banco local efêmero nem cookies inseguros.
: "${CT_DB:?Configure CT_DB no caminho do disco persistente (ex.: /var/data/ctpulse.sqlite3)}"
if [[ "${CT_SECURE_COOKIE:-0}" != "1" ]]; then
  echo "Defina CT_SECURE_COOKIE=1 para acesso HTTPS." >&2
  exit 1
fi

# O schema usa CREATE TABLE IF NOT EXISTS; não popula usuários de demonstração.
python server.py init
exec gunicorn --bind "0.0.0.0:${PORT:-10000}" --workers 2 server:app
