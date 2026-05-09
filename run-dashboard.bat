@echo off
REM Bank Stock Analyzer launcher.
REM Double-click this to start the dashboard. It activates the virtual
REM environment and runs Streamlit, then opens your browser.

cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo [setup] No virtual environment found at .venv. Creating one...
    python -m venv .venv || goto :error
    call .venv\Scripts\activate.bat
    echo [setup] Installing dependencies...
    pip install -r requirements.txt || goto :error
) else (
    call .venv\Scripts\activate.bat
)

REM Streamlit auto-opens the browser by default; --server.headless=false ensures it.
streamlit run streamlit_app.py --server.headless=false

goto :eof

:error
echo.
echo [error] Setup failed. See messages above.
pause
exit /b 1
