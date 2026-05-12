# SubAudit — CLAUDE.md
## Инструкции для Claude Code

---

## Главный документ

**Спецификация:** `SubAudit_Spec_v2_9.docx` в корне проекта.
Все решения строго по ней. Никакой самодеятельности.
Всегда ссылайся на конкретные разделы (Section 4, Section 12 и т.д.).

---

## Кто я и что строю

Я — начинающий разработчик, разрабатываю **SubAudit** —
SaaS веб-приложение для аналитики подписок.
Целевая аудитория: англоязычные B2B пользователи.

**Язык интерфейса:** английский (весь текст, который видит пользователь).
**Язык комментариев в коде:** русский (только для меня как разработчика).

---

## Технический стек

| Компонент | Версия / Сервис |
|-----------|----------------|
| Python | 3.11.9 (pinned) |
| Фреймворк | Streamlit 1.35.0 |
| БД / Авторизация | Supabase (magic link, без паролей) |
| Платежи | Gumroad |
| Ошибки / Мониторинг | Sentry |
| PDF | ReportLab 4.1.0 |
| Fuzzy matching | rapidfuzz 3.9.3 (НЕ fuzzywuzzy) |
| Хостинг | Streamlit Community Cloud |
| Репозиторий | https://github.com/mysubaudit/subaudit |
| Деплой URL | subaudit.streamlit.app |
| Локальная папка | `D:\Программирование\Проекты\SubAudit\` |
| ОС разработчика | Windows, запуск через `run.bat` |

---

## Структура файлов (Section 4 спецификации)

```
app/
├── main.py
├── pages/
│   ├── 1_landing.py
│   ├── 2_upload.py
│   ├── 3_mapping.py
│   ├── 4_cleaning.py
│   ├── 5_dashboard.py
│   ├── 6_pricing.py
│   ├── 7_account.py
│   └── auth_callback.py
├── core/
│   ├── mapper.py
│   ├── cleaner.py
│   ├── metrics.py
│   ├── forecast.py
│   └── simulation.py
├── reports/
│   ├── pdf_builder.py
│   └── excel_builder.py
├── auth/
│   └── supabase_auth.py
├── payments/
│   └── gumroad.py
└── observability/
    └── logger.py
tests/
.github/workflows/supabase_ping.yml
runtime.txt
requirements.txt
```

---

## ВАЖНОЕ ИЗМЕНЕНИЕ: Lemon Squeezy → Gumroad

**Причина:** Lemon Squeezy отказал в регистрации аккаунта.

- Файл `app/payments/lemon_squeezy.py` **УДАЛЁН**
- Создан `app/payments/gumroad.py` — та же функция:
  `get_subscription_status(user_email: str) -> 'free' | 'starter' | 'pro'`
- Все требования Section 13 спецификации соблюдены без изменений
- Во всех файлах импорт заменён на `from app.payments.gumroad import ...`

**Секреты в Streamlit Cloud (Section 19):**
```toml
GUMROAD_ACCESS_TOKEN = "..."
GUMROAD_STARTER_PRODUCT_ID = "starter"
GUMROAD_PRO_PRODUCT_ID = "pro"
```

---

## Текущий статус

### ✅ Проверено и готово к коммиту
| Файл | Статус |
|------|--------|
| `app/pages/1_landing.py` | ✅ |
| `app/pages/2_upload.py` | ✅ |
| `app/pages/3_mapping.py` | ✅ |
| `app/pages/4_cleaning.py` | ✅ |
| `app/pages/5_dashboard.py` | ✅ |
| `app/pages/6_pricing.py` | ✅ |
| `app/pages/7_account.py` | ✅ |
| `app/pages/auth_callback.py` | ✅ |
| `app/payments/gumroad.py` | ✅ |

### ⏳ Ещё не проверено
| Файл | Что проверить |
|------|--------------|
| `app/auth/supabase_auth.py` | Section 12; нет упоминаний Lemon Squeezy |
| `app/observability/logger.py` | Section 7; нет PII в логах |
| `app/reports/pdf_builder.py` | Section 5; нет упоминаний Lemon Squeezy |
| `app/reports/excel_builder.py` | Section 5; нет упоминаний Lemon Squeezy |
| `app/core/*.py` | Иммутабельность, Section 5–11 |
| `tests/` | Полный тест-сьют, Section 17 |

---

## Ключевые правила (обязательно соблюдать)

1. **Спецификация — главный документ.** Все решения строго по v2.9.
2. **Иммутабельность DataFrame** — никаких мутаций (кроме `cleaner.py`). Проверяется через AST в `test_immutability.py`.
3. **Без записи на диск** — PDF и Excel только через `io.BytesIO`.
4. **`.env` и `secrets.toml`** — никогда не коммитить в git.
5. **DEV-override** — только локально через `DEV_OVERRIDE_PLAN` и `DEV_OVERRIDE_EMAIL` в `.env`. На Streamlit Cloud не устанавливать.
6. **Стиль работы** — шаг за шагом, ждать подтверждения после каждого шага.
7. **Ответы** — коротко, по существу, на русском языке.

---

## Порядок оставшейся работы

```
1. Проверить supabase_auth.py, logger.py, pdf_builder.py, excel_builder.py
2. Проверить app/core/*.py на иммутабельность
3. Один git commit со всеми исправлениями
4. Запустить полный тест-сьют (Section 17)
5. Деплой: GitHub → Streamlit Cloud Secrets → проверка
```

---

*Этот файл читается Claude Code автоматически при каждом запуске.*
*Спецификация v2.9 (`SubAudit_Spec_v2_9.docx`) остаётся главным документом.*
