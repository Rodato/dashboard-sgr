#!/bin/bash

# Script para ejecutar Dashboard SGR
# Autor: Daniel Otero
# Fecha: $(date 2025-06-25)

echo "🚀 Iniciando Dashboard SGR..."
echo "📂 Navegando al directorio del proyecto..."

# Navegar al directorio del proyecto
cd /Users/daniel/Desktop/OctopusDash

# Verificar que el directorio existe
if [ ! -d ".venv" ]; then
    echo "❌ Error: No se encuentra el entorno virtual (.venv)"
    echo "💡 Asegúrate de estar en el directorio correcto"
    exit 1
fi

# Verificar que el archivo dashboard existe
if [ ! -f "dashboard_sgr.py" ]; then
    echo "❌ Error: No se encuentra dashboard_sgr.py"
    echo "📋 Archivos disponibles:"
    ls -la *.py 2>/dev/null || echo "No hay archivos .py"
    exit 1
fi

echo "✅ Entorno virtual encontrado"
echo "🔄 Activando entorno virtual..."

# Activar entorno virtual
source .venv/bin/activate

echo "✅ Entorno virtual activado"
echo "🔍 Verificando instalación de Streamlit..."

# Verificar que streamlit está instalado
if ! python -m pip show streamlit > /dev/null 2>&1; then
    echo "❌ Streamlit no está instalado"
    echo "📦 Instalando dependencias..."
    python -m pip install -r requirements.txt
fi

echo "✅ Streamlit verificado"
echo "🌐 Iniciando dashboard..."
echo "🔗 La dashboard estará disponible en: http://localhost:8501"
echo "⏹️  Para detener: Ctrl+C"
echo ""

# Ejecutar streamlit
python -m streamlit run dashboard_sgr.py
