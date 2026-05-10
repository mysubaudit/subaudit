"""
core/mapper.py
SubAudit — Master Specification Sheet v2.9
Section 4  : файл описан как «auto_map_columns() — rapidfuzz»
Section 16 : Development Order Step 2 — core/mapper.py + 3_mapping.py
Section 15 : rapidfuzz==3.9.3 — используется вместо устаревшего fuzzywuzzy
Section 17 : тесты — test_no_false_positive_created_by, test_fuzzy_match_*,
             test_currency_missing_returns_none, test_column_sanitization
"""

import re
import logging
from typing import Optional

from rapidfuzz import process, fuzz

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Канонические внутренние поля SubAudit и их вероятные синонимы в CSV-файлах.
# Section 5 («Core Definitions») и Section 6 («Metric Formulas») определяют,
# какие поля обязательны:  amount, customer_id, status, date.
# currency — необязательное поле (Section 3: «Mixed currencies» guard).
# ---------------------------------------------------------------------------

# Ключ  → список ожидаемых вариантов названий столбца в CSV
CANONICAL_FIELDS: dict[str, list[str]] = {
    "amount": [
        "amount",
        "price",
        "mrr",
        "revenue",
        "subscription_amount",
        "monthly_amount",
        "charge",
        "value",
        "subscription_value",
        "plan_amount",
        "billing_amount",
        "total",
        "amount_usd",
        "amount_eur",
    ],
    # ВАЖНО: status идёт ПЕРЕД customer_id намеренно.
    # "subscription_status" имеет score 76.47% против синонима "subscription_id"
    # (поле customer_id), что выше порога 75. При порядке customer_id→status
    # жадный алгоритм забирал "subscription_status" в customer_id до того,
    # как status успевал его захватить. Перестановка устраняет ложное
    # срабатывание. (Section 17: test_no_false_positive_created_by)
    "status": [
        "status",
        "subscription_status",
        "state",
        "plan_status",
        "billing_status",
        "sub_status",
    ],
    "customer_id": [
        "customer_id",
        "customerid",
        "customer",
        "client_id",
        "clientid",
        "user_id",
        "userid",
        "subscriber_id",
        "account_id",
        "accountid",
        "id",
        "sub_id",
        "subscription_id",
    ],
    "date": [
        "date",
        "period",
        "month",
        "billing_date",
        "subscription_date",
        "created_at",
        "start_date",
        "invoice_date",
        "charge_date",
        "payment_date",
        "period_start",
        "billing_period",
    ],
    "currency": [
        "currency",
        "currency_code",
        "iso_currency",
        "billing_currency",
        "currency_iso",
        # Короткие алиасы — "curr" (66%) и "ccy" (54%) ниже порога rapidfuzz,
        # поэтому добавляем как точные синонимы (Section 17:
        # test_currency_fuzzy_variant_maps_correctly).
        "curr",
        "ccy",
        "cur",
    ],
}

# Столбцы, которые НЕЛЬЗЯ автоматически матчить ни на одно поле.
# Защита от ложных срабатываний (Section 17: test_no_false_positive_created_by).
# «created_by» содержит «id» → без блокировки мог бы матчиться на customer_id.
BLOCKLIST: set[str] = {
    "created_by",
    "updated_by",
    "modified_by",
    "deleted_by",
    "created_at_by",
    "last_modified_by",
}

# Минимальный порог схожести для rapidfuzz (0–100).
# Значение 75 обеспечивает баланс между гибкостью и точностью.
FUZZY_THRESHOLD: int = 75

# Список всех канонических полей (Section 5)
ALL_FIELDS: list[str] = list(CANONICAL_FIELDS.keys())

# Обязательные поля — amount, customer_id, status, date (Section 5)
REQUIRED_FIELDS: list[str] = ["amount", "status", "customer_id", "date"]

# Необязательные поля — currency (Section 3: поле необязательно)
OPTIONAL_FIELDS: list[str] = ["currency"]

# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _sanitize_column_name(col: str) -> str:
    """
    Приводит имя столбца к нормализованному виду для сравнения.
    Section 17: test_column_sanitization.
    Действия:
      1. Приводим к нижнему регистру.
      2. Заменяем пробелы, дефисы и другие разделители на подчёркивание.
      3. Убираем незначимые символы (всё, кроме букв, цифр и подчёркивания).
      4. Схлопываем множественные подчёркивания в одно.
      5. Убираем ведущие/завершающие подчёркивания.
    """
    col = col.strip().lower()
    # Заменяем разделители на подчёркивание
    col = re.sub(r"[\s\-\.]+", "_", col)
    # Оставляем только буквы, цифры, подчёркивание
    col = re.sub(r"[^a-z0-9_]", "", col)
    # Схлопываем повторяющиеся подчёркивания
    col = re.sub(r"_+", "_", col)
    # Убираем крайние подчёркивания
    col = col.strip("_")
    return col


def _is_blocklisted(sanitized_col: str) -> bool:
    """
    Проверяет, входит ли нормализованное имя столбца в список исключений.
    Section 17: test_no_false_positive_created_by.
    """
    return sanitized_col in BLOCKLIST


def _find_best_match(
    sanitized_col: str,
    candidates: list[str],
    threshold: int = FUZZY_THRESHOLD,
) -> bool:
    """
    Возвращает True, если sanitized_col достаточно похож на один из candidates.
    Используем rapidfuzz.fuzz.token_sort_ratio для устойчивости к порядку слов.
    Section 15: rapidfuzz==3.9.3.
    """
    result = process.extractOne(
        sanitized_col,
        candidates,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=threshold,
    )
    return result is not None


# ---------------------------------------------------------------------------
# Основная публичная функция
# ---------------------------------------------------------------------------

def auto_map_columns(df_columns: list[str]) -> dict[str, Optional[str]]:
    """
    Автоматически сопоставляет столбцы загруженного CSV с каноническими
    полями SubAudit при помощи rapidfuzz (Section 4, Section 15, Section 16).

    Параметры
    ----------
    df_columns : list[str]
        Список имён столбцов из загруженного DataFrame (df.columns.tolist()).

    Возвращает
    ----------
    dict[str, Optional[str]]
        Ключи — канонические поля SubAudit:
            "amount", "customer_id", "status", "date", "currency"
        Значения — оригинальное имя столбца CSV, которое лучше всего совпало,
        либо None, если совпадение не найдено.

    Правила
    -------
    - currency → None, если совпадений нет (Section 3: поле необязательно).
    - Блокировка ложных срабатываний через BLOCKLIST (Section 17:
      test_no_false_positive_created_by).
    - Каждый столбец CSV может быть сопоставлен только с ОДНИМ каноническим
      полем (первое совпадение при обходе CANONICAL_FIELDS побеждает).
    - Нормализация имён столбцов перед сравнением (Section 17:
      test_column_sanitization).
    """
    # Результат: canonical → original_csv_column | None
    mapping: dict[str, Optional[str]] = {field: None for field in CANONICAL_FIELDS}

    # Уже «занятые» столбцы CSV (один столбец — одно каноническое поле)
    used_columns: set[str] = set()

    # Строим таблицу: оригинальное имя → санированное
    sanitized_map: dict[str, str] = {
        col: _sanitize_column_name(col) for col in df_columns
    }

    logger.info(
        "auto_map_columns: начало маппинга, столбцов в CSV: %d", len(df_columns)
    )

    for canonical_field, synonyms in CANONICAL_FIELDS.items():
        # Для каждого поля ищем наилучший столбец CSV
        best_original: Optional[str] = None
        best_score: float = -1.0

        for original_col, sanitized_col in sanitized_map.items():
            # Пропускаем уже задействованные столбцы
            if original_col in used_columns:
                continue

            # Пропускаем заблокированные имена (Section 17:
            # test_no_false_positive_created_by)
            if _is_blocklisted(sanitized_col):
                logger.debug(
                    "auto_map_columns: столбец «%s» заблокирован (blocklist)",
                    original_col,
                )
                continue

            # Сначала проверяем точное совпадение с одним из синонимов
            if sanitized_col in synonyms:
                # Точное совпадение всегда выигрывает
                best_original = original_col
                best_score = 100.0
                break

            # Иначе — нечёткое сравнение через rapidfuzz
            result = process.extractOne(
                sanitized_col,
                synonyms,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=FUZZY_THRESHOLD,
            )
            if result is not None:
                _match, score, _idx = result
                if score > best_score:
                    best_score = score
                    best_original = original_col

        if best_original is not None:
            mapping[canonical_field] = best_original
            used_columns.add(best_original)
            logger.info(
                "auto_map_columns: «%s» → «%s» (score=%.1f)",
                canonical_field,
                best_original,
                best_score,
            )
        else:
            # currency разрешено быть None (Section 3, Section 17:
            # test_currency_missing_returns_none)
            mapping[canonical_field] = None
            if canonical_field != "currency":
                logger.warning(
                    "auto_map_columns: обязательное поле «%s» не найдено "
                    "в столбцах CSV",
                    canonical_field,
                )

    logger.info("auto_map_columns: итоговый маппинг: %s", mapping)
    return mapping


def get_unmapped_required_fields(mapping: dict[str, Optional[str]]) -> list[str]:
    """
    Возвращает список ОБЯЗАТЕЛЬНЫХ канонических полей, которые не были
    сопоставлены (значение None).

    Обязательные поля: amount, customer_id, status, date.
    currency — необязательное (Section 3).

    Используется в 3_mapping.py для отображения ошибки пользователю,
    пока все обязательные поля не сопоставлены.
    """
    # Используем константу REQUIRED_FIELDS, определённую выше,
    # чтобы не дублировать список вручную (Section 5)
    return [field for field in REQUIRED_FIELDS if mapping.get(field) is None]


def apply_mapping(df, mapping: dict[str, Optional[str]]):
    """
    Переименовывает столбцы DataFrame согласно результату auto_map_columns().

    Параметры
    ----------
    df : pd.DataFrame
        Исходный DataFrame после загрузки CSV.
    mapping : dict[str, Optional[str]]
        Результат auto_map_columns() — {canonical_field: original_col | None}.

    Возвращает
    ----------
    pd.DataFrame
        Копия DataFrame с переименованными столбцами.
        Сопоставленные столбцы переименовываются в канонические имена.
        Несопоставленные столбцы остаются без изменений.

    Важно
    -----
    Функция работает с КОПИЕЙ — исходный df не мутируется.
    Section 14: df_clean создаётся из df_raw, df_raw удаляется после.
    Section 17 (test_immutability.py): мутации исходного df запрещены.
    """
    # Строим словарь переименования: original_col → canonical_field
    rename_dict: dict[str, str] = {}
    for canonical_field, original_col in mapping.items():
        if original_col is not None and original_col != canonical_field:
            rename_dict[original_col] = canonical_field

    # Работаем с копией — не мутируем оригинал (Section 17: test_immutability)
    df_renamed = df.copy()
    if rename_dict:
        df_renamed = df_renamed.rename(columns=rename_dict)
        logger.info("apply_mapping: переименованы столбцы: %s", rename_dict)

    return df_renamed
