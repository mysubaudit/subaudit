"""
core/presets.py
SubAudit — v3.2 Multi-source CSV presets
Подшаг v3.2.1: Каталог сигнатур колонок.

Словарь _PRESET_SIGNATURES содержит канонические имена колонок для
каждого поддерживаемого источника CSV. Каждая сигнатура — это словарь
с ключами customer_id, date, amount, status и их типовыми названиями
в экспорте данного источника.

Назначение: v3.2.2 (detect_preset) будет сравнивать колонки загруженного
CSV с этими сигнатурами, чтобы автоматически определить источник.

Боль пользователя из STRATEGY.md §1 Option B:
  "I can't use Stripe metrics since I have a lot of manual invoices
   that are not reflected"
  — r/SaaS (https://www.reddit.com/r/SaaS/comments/1qdji6a/)

Авто-определение формата убирает трение CSV-first подхода (STRATEGY.md §8.2:
"CSV-first is friction") — пользователь загружает CSV и сразу получает
готовый маппинг без ручного сопоставления колонок.

Таблица поддерживаемых источников
----------------------------------
| # | Источник       | customer_id          | date              | amount            | status              | Примечание                                      |
|---|----------------|----------------------|-------------------|-------------------|---------------------|-------------------------------------------------|
| 1 | Stripe         | customer_id          | created           | amount            | status              | Стандартный экспорт Stripe Payments             |
| 2 | Paddle         | customer_id          | created_at        | amount            | status              | Paddle Billing API export                       |
| 3 | Gumroad        | email / purchaser_email | created_at     | price             | cancelled           | Gumroad Sales CSV; status из cancelled==TRUE    |
| 4 | LemonSqueezy   | customer_email       | created_at        | total             | status              | LemonSqueezy Orders export                      |
| 5 | Chargebee      | customer_id          | started_at        | amount            | status              | Chargebee Subscriptions export                  |
| 6 | Manual         | customer_id          | date              | amount            | status              | Ручной шаблон (рекомендация для ручных счетов)  |

ВАЖНО:
- Это ТОЛЬКО каталог сигнатур. Никакой логики детектирования здесь нет.
- detect_preset() будет добавлен в v3.2.2.
- Сигнатуры основаны на реальных схемах экспорта каждого источника
  (проверены по документации в мае 2026).
- Для Gumroad status определяется по полю cancelled (boolean), которое
  при маппинге преобразуется в voluntary/involuntary через cleaner.py.
"""

# ── Каталог сигнатур ─────────────────────────────────────────────────────
# Ключ — имя пресета (str), значение — словарь {canonical_field: типовое_имя_колонки}
# Все значения — нижний регистр для case-insensitive сравнения.

_PRESET_SIGNATURES: dict[str, dict[str, str]] = {
    "stripe": {
        "customer_id": "customer_id",
        "date": "created",
        "amount": "amount",
        "status": "status",
    },
    "paddle": {
        "customer_id": "customer_id",
        "date": "created_at",
        "amount": "amount",
        "status": "status",
    },
    "gumroad": {
        "customer_id": "email",          # Gumroad использует email как идентификатор
        "date": "created_at",
        "amount": "price",
        "status": "cancelled",           # boolean: TRUE = voluntary churn
    },
    "lemonsqueezy": {
        "customer_id": "customer_email",
        "date": "created_at",
        "amount": "total",
        "status": "status",
    },
    "chargebee": {
        "customer_id": "customer_id",
        "date": "started_at",
        "amount": "amount",
        "status": "status",
    },
    "manual": {
        "customer_id": "customer_id",
        "date": "date",
        "amount": "amount",
        "status": "status",
    },
}

# Список всех известных имён пресетов (удобно для итерации и тестов)
ALL_PRESETS: list[str] = list(_PRESET_SIGNATURES.keys())

# Обязательные поля, которые должны присутствовать в каждой сигнатуре
PRESET_REQUIRED_FIELDS: list[str] = ["customer_id", "date", "amount", "status"]