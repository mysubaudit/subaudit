"@echo off
cd /d D:\Программирование\Проекты\SubAudit
set PYTHONPATH=D:\Программирование\Проекты\SubAudit
call venv\Scripts\activate
python -m pytest tests/ -v --tb=short
pause"