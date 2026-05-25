import os
import sys
import json
import anthropic

# ================================================================
# НАСТРОЙКИ
# ================================================================
PROJECT_ID = "project-2c31135d-a870-4400-afc"
LOCATION   = "us-east5"
MODEL_NAME = "claude-sonnet-4-6"

# ================================================================
# ИНСТРУМЕНТЫ — функции агента
# ================================================================

def list_project_structure() -> str:
    """Показывает структуру файлов и папок проекта."""
    output = []
    for root, dirs, filenames in os.walk("."):
        # Пропускаем служебные папки
        if any(x in root for x in ['.git', 'venv', '.venv', '__pycache__', 'node_modules']):
            continue
        level = root.replace(".", "").count(os.sep)
        indent = " " * 4 * level
        output.append(f"{indent}[Папка] {os.path.basename(root)}/")
        for f in sorted(filenames):
            output.append(f"{' ' * 4 * (level + 1)}{f}")
    return "\n".join(output) if output else "Проект пуст."


def read_file(file_path: str) -> str:
    """Читает содержимое файла."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Ошибка: файл не найден — {file_path}"
    except UnicodeDecodeError:
        return f"Ошибка: файл {file_path} бинарный, не текстовый."
    except Exception as e:
        return f"Ошибка: {str(e)}"


def write_file(file_path: str, content: str) -> str:
    """Записывает содержимое в файл."""
    try:
        # Создаём папки если не существуют (но не для файлов в корне)
        parent_dir = os.path.dirname(file_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Файл '{file_path}' успешно сохранён."
    except PermissionError:
        return f"Ошибка: нет прав на запись — {file_path}"
    except Exception as e:
        return f"Ошибка: {str(e)}"


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Вызывает нужный инструмент по имени."""
    if tool_name == "list_project_structure":
        return list_project_structure()
    elif tool_name == "read_file":
        return read_file(tool_input["file_path"])
    elif tool_name == "write_file":
        return write_file(tool_input["file_path"], tool_input["content"])
    return f"Неизвестный инструмент: {tool_name}"


# ================================================================
# ОПИСАНИЕ ИНСТРУМЕНТОВ ДЛЯ API (формат Anthropic)
# ================================================================
TOOLS = [
    {
        "name": "list_project_structure",
        "description": "Показывает структуру файлов и папок проекта SubAudit. Вызывай первым при любой задаче.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "read_file",
        "description": "Читает содержимое любого файла в проекте.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Путь к файлу, например: app/core/metrics.py"
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "write_file",
        "description": "Создаёт или перезаписывает файл в проекте.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Путь к файлу, например: app/core/metrics.py"
                },
                "content": {
                    "type": "string",
                    "description": "Полное содержимое файла для записи"
                }
            },
            "required": ["file_path", "content"]
        }
    }
]

SYSTEM_PROMPT = """Ты — автономный ИИ-разработчик проекта SubAudit (Python/Streamlit SaaS).
Ты строго следуешь спецификации SubAudit_Spec.docx (Master Spec v2.9).

Алгоритм работы:
1. Получи задачу от пользователя
2. Просмотри структуру проекта через list_project_structure
3. Прочитай нужные файлы через read_file
4. Напиши код согласно спецификации
5. Сохрани файл через write_file
6. Отчитайся: что сделано, какой Section спецификации затронут

Правила кода:
- Комментарии в коде — только на русском языке
- Интерфейс приложения — на английском языке
- Строго следуй именам функций и сигнатурам из спецификации v2.9
- Никакой самодеятельности вне спецификации"""


# ================================================================
# ОСНОВНОЙ АГЕНТ
# ================================================================

def run_agent():
    print("=" * 60)
    print("  SubAudit AI Agent — интерактивный режим")
    print(f"  Модель: {MODEL_NAME} via Vertex AI")
    print(f"  Проект: {PROJECT_ID} | Регион: {LOCATION}")
    print("  Команды: 'exit' или 'quit' для выхода")
    print("=" * 60)
    print()

    # Подключение к Vertex AI через официальный anthropic SDK
    try:
        client = anthropic.AnthropicVertex(
            region=LOCATION,
            project_id=PROJECT_ID
        )
    except Exception as e:
        print(f"Ошибка подключения: {e}")
        sys.exit(1)

    # История сообщений для поддержания контекста беседы
    history = []

    while True:
        try:
            user_input = input("\nВы: ").strip()

            if user_input.lower() in ['exit', 'quit']:
                print("Агент завершает работу. Удачи!")
                break

            if not user_input:
                continue

            # Добавляем сообщение пользователя в историю
            history.append({"role": "user", "content": user_input})

            print("Агент работает...")

            # Агентный цикл — продолжаем пока модель вызывает инструменты
            while True:
                response = client.messages.create(
                    model=MODEL_NAME,
                    max_tokens=8192,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=history
                )

                # Добавляем ответ модели в историю
                history.append({"role": "assistant", "content": response.content})

                # Если модель завершила (нет вызовов инструментов) — выводим ответ
                if response.stop_reason == "end_turn":
                    for block in response.content:
                        if hasattr(block, "text"):
                            print(f"\nАгент:\n{block.text}")
                    break

                # Если модель вызвала инструменты — выполняем их
                if response.stop_reason == "tool_use":
                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            print(f"  [Инструмент] {block.name}({block.input})")
                            result = execute_tool(block.name, block.input)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result
                            })

                    # Возвращаем результаты инструментов в историю
                    history.append({"role": "user", "content": tool_results})
                    # Продолжаем цикл — модель может вызвать ещё инструменты

        except KeyboardInterrupt:
            print("\nСессия прервана (Ctrl+C).")
            break
        except Exception as e:
            print(f"\nОшибка: {e}")


if __name__ == "__main__":
    run_agent()
