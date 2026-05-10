@echo off
REM setup.bat — Run once from C:\Projects\contrarian-app\
REM Requires: Python 3.11, Docker Desktop running, Ollama installed

echo ============================================
echo  Contrarian App — One-Time Setup
echo ============================================

REM 1. Create .env if missing
if not exist .env (
    echo DATABASE_URL=postgresql://postgres:password@localhost:5432/contrarian_db > .env
    echo OPENSEARCH_HOST=localhost >> .env
    echo [OK] .env created
) else (
    echo [SKIP] .env already exists
)

REM 2. Virtual environment
if not exist venv (
    python -m venv venv
    echo [OK] venv created
) else (
    echo [SKIP] venv already exists
)

REM 3. Install ALL dependencies (including psycopg2-binary and sqlalchemy)
call venv\Scripts\activate
pip install -r requirements.txt
echo [OK] dependencies installed

REM 4. Pull Ollama model (ollama must already be running: ollama serve)
ollama pull llama3.2
echo [OK] llama3.2 ready

REM 5. Start Docker services (OpenSearch + Postgres)
docker compose up -d
echo [OK] Docker services starting...
echo     Waiting 40s for services to be healthy...
timeout /t 40 /nobreak >nul

REM 6. Ingest RSS feeds into OpenSearch
python -c "from airflow.dags.rss_ingest import setup_opensearch_index, ingest_rss_logic; setup_opensearch_index(); ingest_rss_logic()"
echo [OK] News ingested into OpenSearch

echo.
echo ============================================
echo  Setup complete. Now run: start.bat
echo ============================================
