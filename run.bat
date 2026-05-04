@echo off
cd /d D:\Программирование\Проекты\SubAudit
set PYTHONPATH=D:\Программирование\Проекты\SubAudit
call venv\Scripts\activate
streamlit run app/main.py --server.port 8501
pause