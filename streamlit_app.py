"""
streamlit_app.py
Entry point для Streamlit Community Cloud.
Импортирует и запускает app/main.py
"""

import sys
from pathlib import Path

# Добавляем корневую папку в PYTHONPATH
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

# Импортируем и запускаем main
from app.main import main

if __name__ == "__main__":
    main()
