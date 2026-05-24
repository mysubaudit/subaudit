import os
import sys
from google import genai
from google.genai import types

# Данные проекта Google Cloud
PROJECT_ID = "project-2c31135d-a870-4400-afc"
LOCATION = "us-central1"

class SubAuditInteractiveAgent:
    def __init__(self):
        self.client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
        # Gemini 2.5 Pro идеально удерживает контекст беседы и код проекта
        self.model_name = "claude-opus-4-7"
        
    # --- ИНСТРУМЕНТЫ (Tools) ---
    def list_project_structure(self) -> str:
        """Показывает структуру файлов и папок в проекте SubAudit."""
        output = []
        for root, dirs, filenames in os.walk("."):
            if any(x in root for x in ['.git', 'venv', '.venv', '__pycache__', 'node_modules']):
                continue
            level = root.replace(".", "").count(os.sep)
            indent = " " * 4 * level
            output.append(f"{indent}[Папка] {os.path.basename(root)}/")
            for f in filenames:
                output.append(f"{" " * 4 * (level + 1)}{f}")
        return "\n".join(output)

    def read_file(self, file_path: str) -> str:
        """Читает содержимое любого файла в проекте."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Ошибка при чтении файла {file_path}: {str(e)}"

    def write_file(self, file_path: str, content: str) -> str:
        """Записывает код или изменения в указанный файл."""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Успешно! Файл {file_path} сохранен/обновлен."
        except Exception as e:
            return f"Ошибка при записи в файл {file_path}: {str(e)}"

    # --- ЗАПУСК ИНТЕРАКТИВНОГО ДИАЛОГА ---
    def start_chat(self):
        print("====================================================")
        print("🤖 [SubAudit Agent] Живой чат с агентом запущен!")
        print("Вы можете давать ему команды (например: 'изучи план и напиши save_snapshot')")
        print("Для выхода введите: exit или quit")
        print("====================================================\n")
        
        my_tools = [self.list_project_structure, self.read_file, self.write_file]
        
        system_prompt = (
            "Ты — автономный ИИ-разработчик и архитектор проекта SubAudit.\n"
            "У тебя есть инструменты для сканирования проекта, чтения и записи файлов.\n"
            "Внимательно слушай указания пользователя. Если он просит реализовать функционал "
            "(например, шаг из v3.3_plan.md или функцию save_snapshot), сначала найди нужные файлы, "
            "прочитай их, напиши качественный код и сохрани его с помощью write_file.\n"
            "После выполнения действия подробно отчитайся, что именно сделано."
        )

        # Создаем сессию чата с сохранением истории и системной инструкцией
        chat = self.client.chats.create(
            model=self.model_name,
            config=types.GenerateContentConfig(
                tools=my_tools,
                system_instruction=system_prompt,
                temperature=0.3
            )
        )

        # Бесконечный цикл общения
        while True:
            try:
                user_input = input("\n👤 Вы: ")
                if user_input.strip().lower() in ['exit', 'quit']:
                    print("🤖 До связи! Удачи в разработке SubAudit.")
                    break
                
                if not user_input.strip():
                    continue

                print("⏳ Агент работает над задачей...")
                response = chat.send_message(user_input)
                
                print("\n🤖 Агент:")
                print(response.text)

            except KeyboardInterrupt:
                print("\n🤖 Сессия прервана пользователем.")
                break
            except Exception as e:
                print(f"\n❌ Произошла ошибка во время выполнения: {e}")

if __name__ == "__main__":
    agent = SubAuditInteractiveAgent()
    agent.start_chat()