#!/usr/bin/env bash
# Migra PostgreSQL desde el servidor remoto documentado al contenedor local (Docker).
#
# Requisitos: Homebrew libpq (pg_dump, pg_restore):
#   brew install libpq
#   export PATH="/opt/homebrew/opt/libpq/bin:$PATH"
#
# Si ves: «no pg_hba.conf entry for host ...» el servidor debe permitir tu IP
# en pg_hba.conf o debes conectarte desde una red/VPN autorizada.
#
# Uso (ajusta contraseñas por entorno):
#   export SRC_PASSWORD='...'   # remoto
#   export DST_PASSWORD='...'   # local (p. ej. nexdms_dev o POSTGRES_PASSWORD)
#   ./scripts/migrate_dwh_from_remote.sh
#
# Variables opcionales: SRC_HOST SRC_PORT SRC_USER SRC_DB DST_HOST DST_PORT DST_USER DST_DB DUMP_FILE

set -euo pipefail

if ! command -v pg_dump >/dev/null 2>&1; then
  if [[ -x "/opt/homebrew/opt/libpq/bin/pg_dump" ]]; then
    export PATH="/opt/homebrew/opt/libpq/bin:$PATH"
  else
    echo "Instala cliente PostgreSQL: brew install libpq" >&2
    exit 1
  fi
fi

SRC_HOST="${SRC_HOST:-74.208.78.55}"
SRC_PORT="${SRC_PORT:-5432}"
SRC_USER="${SRC_USER:-postgres}"
SRC_DB="${SRC_DB:-vgd_dwh_prod_migracion}"
SRC_PASSWORD="${SRC_PASSWORD:-1234}"

DST_HOST="${DST_HOST:-127.0.0.1}"
DST_PORT="${DST_PORT:-5433}"
DST_USER="${DST_USER:-nexdms}"
DST_DB="${DST_DB:-nexdms}"
DST_PASSWORD="${DST_PASSWORD:-nexdms_dev}"

DUMP_FILE="${DUMP_FILE:-${TMPDIR:-/tmp}/vgd_dwh_migracion.dump}"

echo "==> Volcando origen ${SRC_HOST}:${SRC_PORT}/${SRC_DB} -> ${DUMP_FILE}"
export PGPASSWORD="$SRC_PASSWORD"
pg_dump \
  -h "$SRC_HOST" -p "$SRC_PORT" -U "$SRC_USER" -d "$SRC_DB" \
  -Fc \
  --no-owner \
  -f "$DUMP_FILE"

echo "==> Restaurando en destino ${DST_HOST}:${DST_PORT}/${DST_DB}"
export PGPASSWORD="$DST_PASSWORD"
# RESTORE_CLEAN=0 en la primera carga sobre BD vacía si --clean falla; por defecto refresca lo existente.
RESTORE_ARGS=(--no-owner --no-acl --jobs=1 --verbose)
if [[ "${RESTORE_CLEAN:-1}" == "1" ]]; then
  RESTORE_ARGS+=(--clean --if-exists)
fi
pg_restore -h "$DST_HOST" -p "$DST_PORT" -U "$DST_USER" -d "$DST_DB" "${RESTORE_ARGS[@]}" "$DUMP_FILE"

echo "==> Migración terminada. Volcado conservado en: ${DUMP_FILE}"
