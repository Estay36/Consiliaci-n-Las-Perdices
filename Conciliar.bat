@echo off
REM Lanzador para Windows: doble clic para abrir el conciliador en el navegador.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Primera ejecucion: creando entorno e instalando dependencias...
    python -m venv .venv || (echo No se encontro Python. Instalelo desde python.org marcando "Add to PATH". & pause & exit /b 1)
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || (pause & exit /b 1)
)
".venv\Scripts\python.exe" -m streamlit run app.py --server.headless false --browser.gatherUsageStats false
pause
