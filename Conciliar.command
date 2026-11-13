#!/bin/bash
# Lanzador para macOS: doble clic para abrir el conciliador en el navegador.
cd "$(dirname "$0")" || exit 1
if [ ! -x ".venv/bin/python" ]; then
  echo "Primera ejecución: creando entorno e instalando dependencias..."
  python3 -m venv .venv || { echo "No se encontró Python 3. Instálelo desde python.org"; read -r; exit 1; }
  .venv/bin/python -m pip install --upgrade pip >/dev/null
  .venv/bin/python -m pip install -r requirements.txt || { read -r; exit 1; }
fi
.venv/bin/python -m streamlit run app.py --browser.gatherUsageStats false
