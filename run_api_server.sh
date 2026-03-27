#!/bin/bash

# Script para ejecutar el servidor FastAPI de la plataforma
# Inicia la API REST para el frontend Next.js

set -e

echo "🚀 Iniciando servidor VGD Agente IA API..."

# Verificar que estamos en el directorio correcto
if [ ! -d "agente_dwh" ]; then
    echo "❌ Error: directorio agente_dwh no encontrado"
    echo "Ejecuta este script desde la raíz del proyecto"
    exit 1
fi

# Activar entorno virtual
if [ -f ".venv/bin/activate" ]; then
    echo "🐍 Activando entorno virtual..."
    source .venv/bin/activate
else
    echo "⚠️  No se encontró .venv/bin/activate, continuando sin virtualenv"
fi

# Verificar dependencias
echo "📦 Verificando dependencias..."
python -c "import fastapi, uvicorn, pydantic, bcrypt, jwt" 2>/dev/null && echo "✅ Dependencias OK" || {
    echo "❌ Faltan dependencias. Instala con:"
    echo "pip install fastapi uvicorn pydantic python-jose bcrypt"
    exit 1
}

# Configurar variables de entorno
export JWT_SECRET="${JWT_SECRET:-your-secret-key-change-in-production}"
export PLATFORM_DB_URL="${PLATFORM_DB_URL:-postgresql://vgd_user:vgd_pass@localhost:5432/vgd_platform}"

echo "🔧 Configuración:"
echo "  JWT_SECRET: ${JWT_SECRET:0:10}..."
echo "  PLATFORM_DB_URL: ${PLATFORM_DB_URL}"
echo ""

# Ejecutar servidor
echo "🌐 Iniciando servidor en http://localhost:8501"
echo "📚 Documentación API: http://localhost:8501/docs"
echo "🛑 Presiona Ctrl+C para detener"
echo ""

python agente_dwh/api_routes.py