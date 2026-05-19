.\.venv\Scripts\Activate.ps1    
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
