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

# ── Детектор формата CSV (v3.2.2) ────────────────────────────────────────

def detect_preset(df, columns: list[str]) -> str | None:
    """
    Определяет источник CSV по совпадению колонок с каталогом сигнатур.

    Подшаг v3.2.2 (SPEC.md §8).

    Алгоритм:
      1. Приводит все колонки CSV к нижнему регистру.
      2. Для каждого пресета проверяет, что ВСЕ 4 обязательных поля
         (customer_id, date, amount, status) присутствуют в CSV-колонках
         как точное совпадение (case-insensitive) с сигнатурой пресета.
      3. Возвращает имя первого совпавшего пресета.
      4. Если ни один пресет не совпал — возвращает None.

    Параметры
    ----------
    df : pd.DataFrame
        Загруженный DataFrame (нужен для будущих подшагов, например,
        проверки значений в колонках, а не только названий).
    columns : list[str]
        Список имён колонок из df (df.columns.tolist()).

    Возвращает
    ----------
    str | None
        Имя пресета (\"stripe\", \"paddle\", \"gumroad\", \"lemonsqueezy\",
        \"chargebee\", \"manual\") или None, если формат не распознан.

    Правила
    -------
    - Поиск ТОЛЬКО по точному совпадению имён колонок (без fuzzy match).
      Пресеты — это канонические схемы экспорта; если колонки называются
      иначе, лучше вернуть None, чем угадать неверно.
    - Все 4 поля (customer_id, date, amount, status) должны совпасть.
      Частичное совпадение (3 из 4) — это несовпадение.
    - Порядок обхода: как в _PRESET_SIGNATURES (stripe → manual).
      При совпадении с несколькими пресетами возвращается первый.
    - df передан «на будущее»: в v3.2.5 может добавиться проверка
      значений (например, статусы \"canceled\" vs \"cancelled\").
      Сейчас df не используется в теле функции.

    Примеры
    --------
    >>> df = pd.DataFrame(columns=[\"customer_id\", \"created\", \"amount\", \"status\"])
    >>> detect_preset(df, df.columns.tolist())
    \"stripe\"

    >>> df = pd.DataFrame(columns=[\"email\", \"created_at\", \"price\", \"cancelled\"])
    >>> detect_preset(df, df.columns.tolist())
    \"gumroad\"

    >>> df = pd.DataFrame(columns=[\"foo\", \"bar\", \"baz\"])
    >>> detect_preset(df, df.columns.tolist())
    None
    """
    # Приводим все колонки к нижнему регистру для сравнения
    cols_lower: set[str] = {col.strip().lower() for col in columns}

    for preset_name in ALL_PRESETS:
        signature = _PRESET_SIGNATURES[preset_name]
        # Проверяем, что ВСЕ 4 обязательных поля есть среди колонок
        all_found = True
        for field in PRESET_REQUIRED_FIELDS:
            expected_col = signature[field].lower()
            if expected_col not in cols_lower:
                all_found = False
                break
        if all_found:
            return preset_name

    return None


# ── Получение mapping-правил для пресета (v3.2.4) ─────────────────────────

def get_preset_mapping(preset_name: str) -> dict[str, str]:
    """
    Возвращает mapping {canonical_field: csv_column_name} для заданного пресета.

    Подшаг v3.2.4 (SPEC.md §8).

    Используется на странице mapping для предзаполнения selectbox'ов,
    когда формат CSV распознан через detect_preset().

    Параметры
    ----------
    preset_name : str
        Имя пресета ("stripe", "paddle", "gumroad", "lemonsqueezy",
        "chargebee", "manual").

    Возвращает
    ----------
    dict[str, str]
        Словарь с ключами customer_id, date, amount, status и значениями —
        именами колонок CSV, ожидаемыми для данного источника.
        Поле currency всегда отсутствует в пресетах (добавляется отдельно
        через auto_map_columns на mapping-странице).

    Примеры
    --------
    >>> get_preset_mapping("stripe")
    {'customer_id': 'customer_id', 'date': 'created', 'amount': 'amount', 'status': 'status'}

    >>> get_preset_mapping("gumroad")
    {'customer_id': 'email', 'date': 'created_at', 'amount': 'price', 'status': 'cancelled'}

    >>> get_preset_mapping("unknown")
    Traceback (most recent call last):
        ...
    ValueError: Unknown preset: 'unknown'
    """
    if preset_name not in _PRESET_SIGNATURES:
        raise ValueError(f"Unknown preset: '{preset_name}'")
    # Возвращаем копию, чтобы вызывающий код не мог мутировать оригинал
    return dict(_PRESET_SIGNATURES[preset_name])