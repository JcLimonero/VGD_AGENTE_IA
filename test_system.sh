# Script de prueba rápida del sistema completo
# Verifica que frontend, backend y base de datos funcionan

set -e

echo "🧪 Probando sistema VGD Agente IA completo..."
echo ""

# Función para verificar si un puerto está abierto
check_port() {
    local port=$1
    local service=$2
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "✅ $service corriendo en puerto $port"
        return 0
    else
        echo "❌ $service NO está corriendo en puerto $port"
        return 1
    fi
}

# Función para hacer request HTTP
test_endpoint() {
    local url=$1
    local expected_status=${2:-200}
    local description=$3

    if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "^$expected_status$"; then
        echo "✅ $description: $url"
        return 0
    else
        echo "❌ $description: $url (status != $expected_status)"
        return 1
    fi
}

# Verificar dependencias
echo "📦 Verificando dependencias..."

if ! command -v node &> /dev/null; then
    echo "❌ node no encontrado. Instala Node.js"
    exit 1
fi

# Verificar Python en entorno virtual
if [ ! -f ".venv/bin/python" ]; then
    echo "❌ Entorno virtual no encontrado o python no disponible"
    exit 1
fi

echo "✅ Dependencias básicas OK"
echo ""

# Verificar configuración
echo "⚙️  Verificando configuración..."

if [ ! -f ".env" ]; then
    echo "⚠️  .env no encontrado, usando valores por defecto"
else
    echo "✅ .env encontrado"
    # Cargar variables de entorno
    export $(grep -v '^#' .env | xargs)
fi

# Verificar base de datos usando Python
echo "🗄️  Verificando base de datos..."

PLATFORM_DB_URL="${PLATFORM_DB_URL:-postgresql://vgd_user:vgd_pass@localhost:5432/vgd_platform}"

source .venv/bin/activate
.venv/bin/python -c "
import os
import sys
sys.path.append('.')
try:
    from agente_dwh.db_engine import get_platform_db_engine
    from sqlalchemy import text
    engine = get_platform_db_engine()
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1'))
        print('✅ Conexión a BD exitosa')
        # Verificar tablas
        result = conn.execute(text(\"SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE 'platform_%'\"))
        tables = [row[0] for row in result]
        if 'platform_users' in tables:
            print('✅ Tablas de plataforma encontradas')
        else:
            print('❌ Tablas de plataforma NO encontradas. Ejecuta: ./init_platform_db.sh')
except Exception as e:
    print(f'❌ Error conectando a BD: {e}')
    print('   Asegúrate de que PostgreSQL esté corriendo y la BD exista')
"

echo ""

# Verificar servicios corriendo
echo "🌐 Verificando servicios..."

# Backend API
if check_port 8501 "Backend API"; then
    # Test endpoints
    test_endpoint "http://localhost:8501/health" 200 "Health check"
    test_endpoint "http://localhost:8501/docs" 200 "API docs"
else
    echo "   💡 Para iniciar backend: ./run_api_server.sh"
fi

# Frontend
if check_port 3000 "Frontend Next.js"; then
    test_endpoint "http://localhost:3000" 200 "Frontend home"
else
    echo "   💡 Para iniciar frontend: cd frontend && npm run dev"
fi

echo ""

# Test de integración
echo "🔗 Probando integración..."

if check_port 8501 "Backend API" && check_port 3000 "Frontend"; then
    echo "✅ Ambos servicios corriendo - integración posible"

    # Test login
    login_response=$(curl -s -X POST http://localhost:8501/auth/login \
        -H "Content-Type: application/json" \
        -d '{"email": "admin@example.com", "password": "password123"}')

    if echo "$login_response" | grep -q "access_token"; then
        echo "✅ Login API funciona"
    else
        echo "❌ Login API falló"
        echo "   Respuesta: $login_response"
    fi

    # Test chat
    chat_response=$(curl -s -X POST http://localhost:8501/api/agent/chat/public \
        -H "Content-Type: application/json" \
        -d '{"message": "Hola"}')

    if echo "$chat_response" | grep -q "message"; then
        echo "✅ Chat API funciona"
    else
        echo "❌ Chat API falló"
        echo "   Respuesta: $chat_response"
    fi
else
    echo "❌ Servicios no disponibles para test de integración"
fi

echo ""
echo "📋 Resumen:"
echo "   - BD: Verificada con Python"
echo "   - Backend: $(check_port 8501 "API" >/dev/null 2>&1 && echo "✅ OK" || echo "❌ FAIL")"
echo "   - Frontend: $(check_port 3000 "Next.js" >/dev/null 2>&1 && echo "✅ OK" || echo "❌ FAIL")"
echo ""
echo "🎯 Para iniciar todo:"
echo "   1. ./init_platform_db.sh    # Si BD no está lista"
echo "   2. ./run_api_server.sh     # Backend"
echo "   3. cd frontend && npm run dev  # Frontend"
echo ""
echo "🧪 Test completado!"