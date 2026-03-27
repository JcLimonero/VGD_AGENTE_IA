#!/usr/bin/env python3

import os
import sys

# Cargar .env manualmente
with open('.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            key, value = line.split('=', 1)
            os.environ[key] = value

print('AGENTE_DWH_SKIP_DB_NAME_CHECK:', os.environ.get('AGENTE_DWH_SKIP_DB_NAME_CHECK'))
print('DWH_URL:', os.environ.get('DWH_URL'))
print('PLATFORM_DB_URL:', os.environ.get('PLATFORM_DB_URL'))

from agente_dwh.db_engine import get_platform_db_engine
from sqlalchemy import text

try:
    engine = get_platform_db_engine()
    with open('create_platform_tables.sql', 'r') as f:
        sql = f.read()

    # Ejecutar todo el SQL de una vez
    with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as conn:
        conn.execute(text(sql))
        print('✅ Tablas de plataforma creadas')
except Exception as e:
    print(f'❌ Error creando tablas: {e}')
    sys.exit(1)