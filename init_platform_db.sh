#!/bin/bash

# Script para inicializar la base de datos de la plataforma
# Ejecuta las tablas SQL necesarias para el dashboard

set -e

echo "🚀 Inicializando base de datos de plataforma..."

# Verificar que estamos en el directorio correcto
if [ ! -f "create_platform_tables.sql" ]; then
    echo "❌ Error: create_platform_tables.sql no encontrado"
    echo "Ejecuta este script desde la raíz del proyecto"
    exit 1
fi

# Verificar que tenemos psql
if ! command -v psql &> /dev/null; then
    echo "❌ Error: psql no está instalado"
    echo "Instala PostgreSQL client: brew install postgresql (macOS) o apt install postgresql-client (Ubuntu)"
    exit 1
fi

# Obtener URL de la base de datos
if [ -z "$PLATFORM_DB_URL" ]; then
    echo "⚠️  PLATFORM_DB_URL no definida, usando valor por defecto"
    PLATFORM_DB_URL="postgresql://vgd_user:vgd_pass@localhost:5432/vgd_platform"
fi

echo "📊 Conectando a: $PLATFORM_DB_URL"
echo "🛠️  Ejecutando script de creación de tablas..."

# Ejecutar el script SQL
psql "$PLATFORM_DB_URL" -f create_platform_tables.sql

if [ $? -eq 0 ]; then
    echo "✅ Base de datos inicializada correctamente!"
    echo ""
    echo "📋 Tablas creadas:"
    echo "  - platform_users (usuarios)"
    echo "  - saved_queries (consultas guardadas)"
    echo "  - dashboards (dashboards)"
    echo "  - dashboard_widgets (widgets)"
    echo "  - query_snapshots (snapshots de resultados)"
    echo "  - refresh_log (log de refrescos)"
    echo ""
    echo "👤 Usuario de prueba creado:"
    echo "  Email: admin@example.com"
    echo "  Password: password123"
    echo ""
    echo "🎯 Próximo paso: Ejecutar el servidor API"
    echo "  python agente_dwh/api_routes.py"
else
    echo "❌ Error al inicializar la base de datos"
    exit 1
fi