# SubAudit — CLAUDE.md
## Инструкции для Claude Code и других AI-ассистентов

**Последнее обновление:** 2026-05-13

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
| Excel | openpyxl 3.1.2 |
| Fuzzy matching | rapidfuzz 3.9.3 (НЕ fuzzywuzzy) |
| Encoding detection | charset-normalizer (НЕ chardet) |
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
SUPABASE_URL = "..."
SUPABASE_KEY = "..."
SENTRY_DSN = "..."
```

---

## Текущий статус проекта

### ✅ ЗАВЕРШЕНО И ЗАДЕПЛОЕНО (2026-05-13)

#### Основные страницы и функционал
| Компонент | Статус | Примечания |
|-----------|--------|-----------|
| `app/pages/1_landing.py` | ✅ | Landing page с описанием продукта |
| `app/pages/2_upload.py` | ✅ | CSV загрузка с оптимизацией encoding detection (100KB sample) |
| `app/pages/3_mapping.py` | ✅ | Маппинг колонок с fuzzy matching |
| `app/pages/4_cleaning.py` | ✅ | Очистка данных с детальным отчётом |
| `app/pages/5_dashboard.py` | ✅ | Дашборд с метриками, прогнозом, симуляцией |
| `app/pages/6_pricing.py` | ✅ | Страница тарифов с Gumroad интеграцией |
| `app/pages/7_account.py` | ✅ | Личный кабинет с управлением подпиской |
| `app/pages/auth_callback.py` | ✅ | Supabase OAuth callback |

#### Core модули
| Компонент | Статус | Примечания |
|-----------|--------|-----------|
| `app/core/metrics.py` | ✅ | Все метрики Block 1-5 + промежуточные значения для Excel |
| `app/core/forecast.py` | ✅ | HoltWinters прогноз с gate ≥3 месяцев |
| `app/core/simulation.py` | ✅ | PRO-only симуляция подписок |
| `app/core/mapper.py` | ✅ | Fuzzy matching колонок |
| `app/core/cleaner.py` | ✅ | Очистка данных с иммутабельностью |

#### Отчёты
| Компонент | Статус | Примечания |
|-----------|--------|-----------|
| `app/reports/pdf_builder.py` | ✅ | PDF с watermark для FREE, 8 когорт в Block 5 |
| `app/reports/excel_builder.py` | ✅ | Excel с рабочими формулами, forecast при ≥3 мес |

#### Интеграции
| Компонент | Статус | Примечания |
|-----------|--------|-----------|
| `app/payments/gumroad.py` | ✅ | Проверка подписки с кэшированием 5 мин |
| `app/auth/supabase_auth.py` | ✅ | Magic link авторизация |
| `app/observability/logger.py` | ✅ | Sentry с PII-фильтрацией |

---

## Последние исправления (2026-05-13)

### 1. Excel-отчёт — 3 исправления
- ✅ **Forecast sheet** теперь заполняется при ≥3 месяцах данных (было: пустой при 3-5 мес)
- ✅ **Metrics Detail формулы** работают: ARR, ARPU, Growth Rate, Churn Rate, NRR, LTV, Lost Subs
  - Добавлены промежуточные значения: `mrr_prev_month`, `active_subscribers_prev_month`, `expansion_mrr`
- ✅ **Data Quality описания** улучшены для понятности пользователя

### 2. PDF-отчёт — 1 исправление
- ✅ **Block 5 Cohort Table** оптимизирован:
  - 8 когорт вместо 3 (больше истории)
  - Шрифт 7pt (читаемый, компактный)
  - Добавлена легенда: "How to read: Each cohort shows % of customers retained..."

### 3. CSV загрузка — 4 улучшения
- ✅ **Encoding detection** оптимизирован: анализ только первых 100KB (ускорение)
- ✅ **Прогресс-бары** добавлены: "Loading file...", "Parsing CSV..."
- ✅ **Обработка ошибок** улучшена: детальные сообщения для EmptyDataError, ParserError, UnicodeDecodeError
- ✅ **on_bad_lines='warn'** добавлен: pandas не падает на проблемных строках

### 4. Dashboard — 1 критическое исправление
- ✅ **generate_excel() вызов** исправлен: правильные параметры `metrics_dict`, `cohort_df`, `data_quality_flags`, `user_plan`

---

## Известные ограничения (из спецификации)

1. **Cohort retention** (Section 7) — intentional asymmetry:
   - Retention считается по наличию строки (любой статус), не по amount
   - Paused/discounted подписки считаются retained

2. **LTV cap** (Section 6) — 36 месяцев:
   - Если churn_rate = 0, LTV = ARPU × 36
   - НЕ использовать для unit economics или CAC payback

3. **NRR > 200%** (Section 6) — предупреждение:
   - Обычно из-за ограниченных данных prev_month
   - Показывается warning в UI и отчётах

4. **Simulation ARPU homogeneity** (Section 11) — KNOWN LIMITATION:
   - Предполагает uniform ARPU
   - С mixed pricing tiers отклонение 30-60%
   - Mixed-tier modelling в roadmap v2

5. **Forecast gate** (Section 10):
   - <3 месяцев → не показывается
   - 3-5 месяцев → только Realistic сценарий с предупреждением
   - ≥6 месяцев → все 3 сценария (Pessimistic, Realistic, Optimistic)

---

## Ключевые правила (обязательно соблюдать)

1. **Спецификация — главный документ.** Все решения строго по v2.9.
2. **Иммутабельность DataFrame** — никаких мутаций (кроме `cleaner.py`). Проверяется через AST в `test_immutability.py`.
3. **Без записи на диск** — PDF и Excel только через `io.BytesIO`.
4. **`.env` и `secrets.toml`** — никогда не коммитить в git.
5. **DEV-override** — только локально через `DEV_OVERRIDE_PLAN` и `DEV_OVERRIDE_EMAIL` в `.env`. На Streamlit Cloud не устанавливать.
6. **Стиль работы** — шаг за шагом, ждать подтверждения перед изменениями.
7. **Ответы** — коротко, по существу, на русском языке.
8. **Перед изменениями** — всегда задавать вопросы для уточнения требований.

---

## Workflow для AI-ассистента

### При получении задачи:
1. Прочитать спецификацию `SubAudit_Spec_v2_9.docx` (если доступна)
2. Проверить текущий статус в этом файле
3. Задать уточняющие вопросы перед изменениями
4. Получить подтверждение от разработчика
5. Внести изменения
6. Создать коммит с описанием на русском + Co-Authored-By
7. Обновить этот файл (CLAUDE.md) при необходимости

### Стиль коммитов:
```
fix: краткое описание на русском

Детальное описание изменений:
- Что исправлено
- Почему это было нужно
- Какие Section спецификации затронуты

Co-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>
```

---

## Что делать при ошибках

### Если пользователь сообщает об ошибке:
1. Проверить логи Sentry (если доступны)
2. Воспроизвести локально через `run.bat`
3. Проверить соответствие спецификации
4. Предложить решение с объяснением
5. Получить подтверждение перед исправлением

### Типичные проблемы:
- **Excel generation failed** → проверить сигнатуру `generate_excel()` и параметры
- **Forecast пустой** → проверить `forecast_dict` в `session_state`
- **CSV не загружается** → проверить encoding detection и обработку ошибок
- **Метрики N/A** → проверить `prev_month_status` в `data_quality_flags`

---

## Следующие шаги (если потребуется)

### Потенциальные улучшения:
1. **Тесты** — запустить полный тест-сьют (Section 17)
2. **Производительность** — профилирование на больших файлах (50K строк)
3. **UX** — A/B тестирование landing page
4. **Аналитика** — добавить tracking пользовательских действий
5. **Документация** — создать user guide для пользователей

### Roadmap v2 (из спецификации):
- Mixed-tier ARPU modelling для Simulation
- Экспорт в Google Sheets
- API для интеграций
- Webhooks для автоматической загрузки данных

---

*Этот файл читается Claude Code и другими AI-ассистентами автоматически.*
*Спецификация v2.9 (`SubAudit_Spec_v2_9.docx`) остаётся главным документом.*
*При любых сомнениях — спрашивай разработчика перед изменениями.*
