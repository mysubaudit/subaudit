"""
app/core/cleaner.py
-------------------
Модуль очистки данных. Реализован строго по Master Specification Sheet v2.9.
Используемые разделы: Section 3 (Data Limits & Validation), Section 5 (Core Definitions),
Section 14 (Session State & Memory), Section 4 (Project File Structure).

Development Order Step 3: core/cleaner.py + 4_cleaning.py (threading.Timer timeout).
Данный файл реализует только core/cleaner.py.
"""

import pandas as pd
from charset_normalizer import from_bytes
import streamlit as st
from typing import Tuple


# ---------------------------------------------------------------------------
# Вспомогательные константы — нормализация статусов (Section 3, test_cleaner.py)
# ---------------------------------------------------------------------------
# Допустимые значения статуса после нормализации
_VALID_STATUSES = {"active", "churned", "trial"}

# Карта нормализации: приводим распространённые варианты к стандарту
_STATUS_NORMALIZATION_MAP: dict[str, str] = {
    # active
    "active": "active",
    "Active": "active",
    "ACTIVE": "active",
    # churned
    "churned": "churned",
    "Churned": "churned",
    "CHURNED": "churned",
    "canceled": "churned",
    "cancelled": "churned",
    "Canceled": "churned",
    "Cancelled": "churned",
    # trial
    "trial": "trial",
    "Trial": "trial",
    "TRIAL": "trial",
}


def clean_data(df_raw: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    """
    Очищает сырой DataFrame и возвращает (df_clean, cleaning_report).

    Параметры
    ----------
    df_raw : pd.DataFrame
        Исходный датафрейм после маппинга колонок (из 3_mapping.py).
        Ожидаемые колонки после маппинга: customer_id, date, status, amount, currency (опц.).

    Возвращает
    ----------
    df_clean : pd.DataFrame
        Очищенный датафрейм. Строки с amount == 0 и amount < 0 НЕ удаляются из df_clean
        (Section 3: «Do NOT remove from df_clean»), но исключаются из MRR-расчётов
        в metrics.py.
    cleaning_report : dict
        Отчёт об операциях очистки:
            - duplicates_removed (int)
            - zero_amount_rows (int)
            - negative_amount_rows (int)
            - rows_before (int)
            - rows_after (int)
            - encoding_warning (bool)
            - multicurrency_error (bool)

    Raises
    ------
    ValueError
        Если датафрейм содержит смешанные валюты (Section 3: «block processing»).
    """

    # ------------------------------------------------------------------
    # Шаг 0: Инициализация отчёта
    # ------------------------------------------------------------------
    cleaning_report: dict = {
        "duplicates_removed": 0,
        "zero_amount_rows": 0,
        "negative_amount_rows": 0,
        "rows_before": len(df_raw),
        "rows_after": 0,
        "encoding_warning": False,
        "multicurrency_error": False,
    }

    # Работаем с копией — не мутируем входной df_raw (Section 14: иммутабельность)
    # Исключение: cleaner.py может применять subscript-мутации при сборке df_clean из df_raw
    df = df_raw.copy()

    # ------------------------------------------------------------------
    # Шаг 1: Удаление точных дубликатов (Section 3: «Remove exact duplicates»)
    # «Report in cleaning_report['duplicates_removed']»
    # ------------------------------------------------------------------
    rows_before_dedup = len(df)
    df = df.drop_duplicates()
    cleaning_report["duplicates_removed"] = rows_before_dedup - len(df)

    # ------------------------------------------------------------------
    # Шаг 2: Нормализация колонки status (test_cleaner.py: test_status_normalization_*)
    # Приводим к нижнему регистру стандартным маппингом
    # ------------------------------------------------------------------
    if "status" in df.columns:
        df["status"] = (
            df["status"]
            .astype(str)
            .str.strip()
            .map(lambda s: _STATUS_NORMALIZATION_MAP.get(s, s.lower()))
        )

    # ------------------------------------------------------------------
    # Шаг 3: Нормализация customer_id — строка без пробелов
    # ------------------------------------------------------------------
    if "customer_id" in df.columns:
        df["customer_id"] = df["customer_id"].astype(str).str.strip()

    # ------------------------------------------------------------------
    # Шаг 4: Нормализация колонки date → datetime (Section 5: cohort logic зависит от дат)
    # ------------------------------------------------------------------
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        # Строки с непарсируемой датой — оставляем (NaT), metrics.py их проигнорирует

    # ------------------------------------------------------------------
    # Шаг 5: Нормализация колонки amount → float64
    # Section 3: «No warning — float64 handles up to ~$9 quadrillion accurately»
    # ------------------------------------------------------------------
    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").astype("float64")

    # ------------------------------------------------------------------
    # Шаг 6: Проверка смешанных валют (Section 3: «Mixed currencies»)
    # «If currency column has > 1 unique value: show error, block processing»
    # «Do NOT silently mix»
    # ------------------------------------------------------------------
    if "currency" in df.columns:
        unique_currencies = df["currency"].dropna().unique()
        if len(unique_currencies) > 1:
            cleaning_report["multicurrency_error"] = True
            # Блокируем обработку — показываем ошибку и бросаем исключение
            st.error(
                f"Multiple currencies detected: {', '.join(str(c) for c in unique_currencies)}. "
                "Please upload a file with a single currency. Mixed currencies are not supported."
            )
            raise ValueError(
                f"Mixed currency error: currencies detected: {unique_currencies}. "
                "Processing blocked. "
                "(Section 3: Mixed currency — block processing)"
            )

    # ------------------------------------------------------------------
    # Шаг 7: Фиксация строк с amount == 0 и amount < 0
    # Section 3:
    #   «Amount == 0: Exclude from MRR. Include in cleaning_report. Do NOT remove from df_clean.»
    #   «Amount < 0:  Exclude from MRR. Include in revenue_churn (refunds). Include in cleaning_report.»
    # Сами строки НЕ удаляем — metrics.py фильтрует по «active rows» = status=='active' AND amount > 0
    # ------------------------------------------------------------------
    if "amount" in df.columns:
        cleaning_report["zero_amount_rows"] = int((df["amount"] == 0).sum())
        cleaning_report["negative_amount_rows"] = int((df["amount"] < 0).sum())

    # ------------------------------------------------------------------
    # Шаг 8: Финальный подсчёт строк
    # ------------------------------------------------------------------
    cleaning_report["rows_after"] = len(df)

    df_clean = df.reset_index(drop=True)

    return df_clean, cleaning_report


def detect_encoding(raw_bytes: bytes) -> Tuple[str, bool]:
    """
    Определяет кодировку файла согласно цепочке из Section 3.

    Цепочка зондирования (Section 3 «Encoding detection»):
        charset-normalizer probe → utf-8-sig → utf-8 → cp1251 → latin-1 (last resort)

    Возвращает
    ----------
    encoding : str
        Определённая кодировка.
    latin1_warning : bool
        True, если кодировка определена как latin-1 (нужно показать st.warning).
    """
    # Шаг 1: charset-normalizer как основной детектор (Section 15: charset-normalizer 3.3.2)
    result = from_bytes(raw_bytes).best()
    if result is not None:
        detected = result.encoding
    else:
        detected = None

    # Цепочка fallback-кодировок (Section 3)
    fallback_chain = ["utf-8-sig", "utf-8", "cp1251", "latin-1"]

    if detected:
        # Нормализуем имя кодировки для сравнения
        encoding = detected.lower().replace("-", "_")
        is_latin1 = encoding in ("latin_1", "iso_8859_1", "iso8859_1")
        return detected, is_latin1

    # charset-normalizer не дал результата — пробуем цепочку вручную
    for enc in fallback_chain:
        try:
            raw_bytes.decode(enc)
            is_latin1 = enc == "latin-1"
            return enc, is_latin1
        except (UnicodeDecodeError, LookupError):
            continue

    # Абсолютный fallback — latin-1 всегда декодирует любой байт
    return "latin-1", True


def read_csv_with_encoding(file_bytes: bytes) -> pd.DataFrame:
    """
    Читает CSV из байт с автоматическим определением кодировки (Section 3).
    Показывает st.warning при кодировке latin-1.

    Параметры
    ----------
    file_bytes : bytes
        Содержимое CSV-файла в байтах.

    Возвращает
    ----------
    pd.DataFrame
        Прочитанный датафрейм.

    Raises
    ------
    ValueError
        Если файл не удаётся прочитать ни одной кодировкой.
    """
    import io

    encoding, latin1_warning = detect_encoding(file_bytes)

    # Section 3: «On latin-1: show st.warning() — characters may render incorrectly»
    if latin1_warning:
        st.warning(
            "File encoding detected as latin-1. "
            "Some characters may not render correctly."
        )

    try:
        df = pd.read_csv(io.BytesIO(file_bytes), encoding=encoding)
        return df
    except Exception as exc:
        # ИСПРАВЛЕНО: сообщение об ошибке на английском (user-facing строки — только английский)
        raise ValueError(
            f"Failed to read CSV with encoding '{encoding}': {exc}"
        ) from exc
