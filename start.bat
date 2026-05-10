@echo off
REM start.bat — Run after setup.bat
REM Opens backend and dashboard in separate windows

echo Starting FastAPI backend on http://localhost:8000 ...
start "Contrarian Backend" cmd /k "venv\Scripts\activate && uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 /nobreak >nul

echo Starting Streamlit dashboard on http://localhost:8501 ...
start "Contrarian Dashboard" cmd /k "venv\Scripts\activate && streamlit run app\ui\dashboard.py"

echo.
echo Both services launching in separate windows.
echo Backend:   http://localhost:8000/health
echo Dashboard: http://localhost:8501
