"""
app/pages/2_upload.py
SubAudit — страница загрузки CSV-файла.
Соответствует Master Specification Sheet v2.9, Development Order Step 1.

Разделы спецификации:
  - Section 3  : Data Limits & Validation (лимиты, форматы, кодировка, дубликаты, валюта, суммы)
  - Section 4  : Project File Structure (роль 2_upload.py)
  - Section 5  : Core Definitions («active rows» — используется в пояснении к пользователю)
  - Section 14 : Session State & Memory (ключи df_clean, df_raw, column_mapping, cleaning_report, currency)
  - Section 16 : Development Order Step 1
"""

import time
import streamlit as st
import pandas as pd
from charset_normalizer import from_bytes  # Section 3: charset-normalizer (не chardet)
import io

# Общие UI-утилиты: CSS скрытие авто-навигации + управляемый сайдбар
# app/utils/page_setup.py — аналогичный вызов есть в каждой странице приложения
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from app.utils.page_setup import inject_nav_css, render_sidebar, record_activity
from app.utils.ui_components import render_cta_button

# ---------------------------------------------------------------------------
# set_page_config — ОБЯЗАН быть первым вызовом Streamlit (до inject_nav_css).
# Streamlit требует этого вызова раньше любых st.* — Section 16 Step 1.
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SubAudit — Upload Data",
    page_icon="📂",
    layout="centered",
)

# ---------------------------------------------------------------------------
# Константы (Section 3)
# ---------------------------------------------------------------------------
MAX_FILE_SIZE_BYTES: int = 15 * 1024 * 1024  # 15 МБ
MAX_ROWS: dict[str, int] = {
    "free": 1_000,
    "starter": 10_000,
    "pro": 50_000,
}
ALLOWED_EXTENSION: str = ".csv"

# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _detect_encoding(raw_bytes: bytes) -> tuple[str, bool]:
    """
    Определяет кодировку файла согласно Section 3:
    charset-normalizer → utf-8-sig → utf-8 → cp1251 → latin-1 (последний вариант).
    Возвращает (encoding, is_latin1_fallback).

    Оптимизация: анализируем только первые 100KB для ускорения на больших файлах.
    """
    # Оптимизация: charset-normalizer анализирует только первые 100KB
    sample_size = min(100 * 1024, len(raw_bytes))
    sample = raw_bytes[:sample_size]

    # Шаг 1: Проба через charset-normalizer
    result = from_bytes(sample).best()
    if result is not None:
        detected = result.encoding.lower()
        # Нормализуем алиасы
        if detected in ("utf-8-sig", "utf_8_sig"):
            return "utf-8-sig", False
        if detected in ("utf-8", "utf_8", "ascii"):
            return "utf-8", False
        if detected in ("cp1251", "windows-1251"):
            return "cp1251", False
        # Если charset-normalizer вернул другую кодировку — доверяем ей
        return detected, False

    # Шаг 2: Явный перебор по цепочке (Section 3)
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            sample.decode(enc)
            return enc, False
        except (UnicodeDecodeError, LookupError):
            continue

    # Шаг 3: Последний вариант — latin-1 (Section 3: показать st.warning)
    return "latin-1", True


def _read_csv(raw_bytes: bytes) -> tuple[pd.DataFrame | None, str]:
    """
    Читает CSV из байт с автоопределением кодировки.
    Возвращает (DataFrame или None, сообщение об ошибке).
    При latin-1 показывает st.warning согласно Section 3.
    """
    encoding, is_latin1 = _detect_encoding(raw_bytes)

    if is_latin1:
        # Section 3: при latin-1 — предупреждение (не ошибка, продолжаем)
        # Текст на английском — аудитория англоязычная
        st.warning(
            "⚠️ File encoding detected as latin-1 (fallback). "
            "Some characters may not display correctly."
        )

    try:
        # Прогресс-бар для больших файлов
        with st.spinner(f"Parsing CSV ({encoding})..."):
            df = pd.read_csv(
                io.BytesIO(raw_bytes),
                encoding=encoding,
                low_memory=False,
                on_bad_lines='warn',  # Логируем проблемные строки вместо падения
            )
        return df, ""
    except pd.errors.EmptyDataError:
        return None, "The CSV file is empty or contains no valid data."
    except pd.errors.ParserError as exc:
        return None, f"CSV parsing error: {exc}. Please check the file format."
    except UnicodeDecodeError as exc:
        return None, f"Encoding error ({encoding}): {exc}. The file may be corrupted."
    except Exception as exc:
        return None, f"Unexpected error reading CSV: {exc}"


def _validate_and_truncate(
    df: pd.DataFrame, user_plan: str
) -> tuple[pd.DataFrame | None, str]:
    """
    Проверяет количество строк по лимиту плана и при необходимости усекает df.
    Section 3: показать warning ДО усечения; никогда не блокировать — усекать.
    Возвращает (df_truncated или None, сообщение об ошибке).
    """
    limit = MAX_ROWS.get(user_plan, MAX_ROWS["free"])
    actual = len(df)

    if actual > limit:
        # Section 3: сначала предупреждение, потом усечение. Текст на английском.
        st.warning(
            f"⚠️ Your file contains {actual:,} rows, but the {user_plan.upper()} plan "
            f"allows up to {limit:,} rows. "
            f"Only the first {limit:,} rows will be processed."
        )
        df = df.iloc[:limit].copy()

    return df, ""


def _check_currency(df: pd.DataFrame) -> str | None:
    """
    Section 3: если столбец currency присутствует и содержит > 1 уникального значения —
    вернуть сообщение об ошибке (блокировать обработку).
    """
    # Ищем столбец с именем «currency» (регистронезависимо)
    currency_cols = [c for c in df.columns if c.strip().lower() == "currency"]
    if not currency_cols:
        return None  # Столбец отсутствует — проверка не нужна

    col = currency_cols[0]
    unique_currencies = df[col].dropna().unique()
    if len(unique_currencies) > 1:
        currencies_list = ", ".join(str(c) for c in unique_currencies)
        # Section 3: смешанные валюты — ошибка, блокировать обработку. Текст на английском.
        return (
            f"❌ Your file contains multiple currencies: {currencies_list}. "
            "Mixed currencies are not supported. "
            "Please upload a file with a single currency."
        )
    return None


def _remove_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Section 3: удаляет точные дубликаты строк.
    Возвращает (df_cleaned, количество удалённых дубликатов).
    """
    before = len(df)
    df_clean = df.drop_duplicates()
    removed = before - len(df_clean)
    return df_clean.reset_index(drop=True), removed


def _get_currency_value(df: pd.DataFrame) -> str:
    """
    Извлекает значение валюты из столбца currency (если он есть).
    Section 14: сохраняется в session_state['currency'].
    """
    currency_cols = [c for c in df.columns if c.strip().lower() == "currency"]
    if not currency_cols:
        return "N/A"
    col = currency_cols[0]
    values = df[col].dropna().unique()
    return str(values[0]) if len(values) == 1 else "N/A"


# ---------------------------------------------------------------------------
# Основная логика страницы
# ---------------------------------------------------------------------------

def show_lost_session_guidance() -> None:
    """
    Section 4: 2_upload.py — «lost-session guidance».
    Показывается, если пользователь попал на страницу без df_clean в session_state.
    Текст на английском — аудитория англоязычная.
    """
    if "df_clean" not in st.session_state:
        st.info(
            "ℹ️ No data found in your current session. "
            "If you refreshed the page or opened a new tab, "
            "please upload your CSV file again. "
            "Data is stored in-memory only and is not saved between sessions."
        )


def main() -> None:
    """Точка входа страницы 2_upload.py."""

    # Скрываем автонавигацию Streamlit, показываем управляемый сайдбар
    # (без этого Streamlit показывает все страницы из /pages/ всем пользователям)
    inject_nav_css()
    render_sidebar()

    st.title("📂 Upload Your Data")

    # -----------------------------------------------------------------------
    # Section 3 / Section 4: обязательный notice о конфиденциальности —
    # VERBATIM, как указано в спецификации (ℹ блок в Section 3).
    # -----------------------------------------------------------------------
    st.info(
        "ℹ️ Files are processed in-memory and NEVER stored or sent to third parties."
    )

    # -----------------------------------------------------------------------
    # Подсказка при потерянной сессии (Section 4)
    # -----------------------------------------------------------------------
    show_lost_session_guidance()

    # -----------------------------------------------------------------------
    # Определяем текущий план пользователя (Section 14: user_plan)
    # По умолчанию — free (до аутентификации)
    # -----------------------------------------------------------------------
    user_plan: str = st.session_state.get("user_plan", "free")
    limit_rows: int = MAX_ROWS[user_plan]

    # Информационная строка о лимитах — текст на английском
    st.caption(
        f"Your plan: **{user_plan.upper()}** · "
        f"Row limit: **{limit_rows:,}** · "
        f"Max file size: **15 MB** · "
        f"Format: **.csv only**"
    )

    # -----------------------------------------------------------------------
    # Виджет загрузки файла — 1 файл на сессию (Section 3)
    # Все label/help тексты на английском (пользователь видит эти тексты)
    # -----------------------------------------------------------------------
    uploaded_file = st.file_uploader(
        label="Choose a CSV file with your subscription data",
        type=["csv"],                   # Только .csv (Section 3)
        accept_multiple_files=False,    # Section 3: 1 файл на сессию
        help="Only .csv format is supported. Maximum file size is 15 MB.",
    )

    if uploaded_file is None:
        # Файл ещё не загружен — ждём
        st.stop()

    # -----------------------------------------------------------------------
    # Валидация расширения (Section 3: .csv only)
    # -----------------------------------------------------------------------
    file_name: str = uploaded_file.name
    if not file_name.lower().endswith(ALLOWED_EXTENSION):
        st.error(
            f"❌ Unsupported file format: '{file_name}'. "
            "Please upload a .csv file."
        )
        st.stop()

    # -----------------------------------------------------------------------
    # Чтение файла в память с прогресс-баром (Section 3)
    # -----------------------------------------------------------------------
    with st.spinner("Loading file..."):
        try:
            raw_bytes: bytes = uploaded_file.read()
        except Exception as exc:
            st.error(f"❌ Failed to read file: {exc}. Please try uploading again.")
            st.stop()

    file_size_bytes: int = len(raw_bytes)

    # -----------------------------------------------------------------------
    # Валидация размера файла (Section 3: 15 МБ)
    # -----------------------------------------------------------------------
    if file_size_bytes > MAX_FILE_SIZE_BYTES:
        size_mb = file_size_bytes / (1024 * 1024)
        st.error(
            f"❌ File size ({size_mb:.1f} MB) exceeds the 15 MB limit. "
            "Please reduce the file size and try again."
        )
        st.stop()

    # -----------------------------------------------------------------------
    # Чтение CSV с определением кодировки (Section 3)
    # Прогресс-бар показывается внутри _read_csv()
    # -----------------------------------------------------------------------
    df_raw, read_error = _read_csv(raw_bytes)

    if df_raw is None:
        st.error(f"❌ Could not read the file: {read_error}")
        st.stop()

    if df_raw.empty:
        st.error("❌ The uploaded file contains no data rows.")
        st.stop()

    # -----------------------------------------------------------------------
    # Проверка смешанных валют (Section 3: если > 1 → ошибка, блокировать)
    # -----------------------------------------------------------------------
    currency_error = _check_currency(df_raw)
    if currency_error:
        st.error(currency_error)
        st.stop()

    # -----------------------------------------------------------------------
    # Проверка лимита строк + усечение (Section 3: warning ДО усечения)
    # -----------------------------------------------------------------------
    df_raw, _truncate_error = _validate_and_truncate(df_raw, user_plan)
    # _truncate_error не используется — warning выводится внутри функции

    # -----------------------------------------------------------------------
    # Удаление дубликатов (Section 3)
    # -----------------------------------------------------------------------
    df_processed, duplicates_removed = _remove_duplicates(df_raw)

    # -----------------------------------------------------------------------
    # Сохраняем данные в session_state (Section 14)
    # df_raw должен быть удалён после создания df_clean (Section 14).
    # На этом этапе df_processed — это «сырые» данные после базовой очистки.
    # Полная очистка происходит в core/cleaner.py (Step 3).
    # Сохраняем в df_raw для передачи в mapper (Step 2) и последующую очистку.
    # -----------------------------------------------------------------------
    st.session_state["df_raw"] = df_processed

    # Сбрасываем downstream-ключи при новой загрузке (Section 14)
    for key in (
        "df_clean",
        "column_mapping",
        "cleaning_report",
        "metrics_dict",
        "data_quality_flags",
        "forecast_dict",
        "simulation_dict",
        "currency",
    ):
        st.session_state.pop(key, None)

    # Определяем и сохраняем валюту (Section 14: currency — str)
    currency_value = _get_currency_value(df_processed)
    st.session_state["currency"] = currency_value

    # -----------------------------------------------------------------------
    # Отчёт о базовой предобработке — тексты на английском (пользователь видит)
    # Полный cleaning_report создаётся в core/cleaner.py (Step 3)
    # -----------------------------------------------------------------------
    st.success(f"✅ File '{file_name}' uploaded successfully.")

    # Явное действие пользователя — обновляем last_activity (Section 14)
    record_activity()

    col1, col2, col3 = st.columns(3)
    col1.metric("Rows loaded", f"{len(df_processed):,}")
    col2.metric("Columns", f"{len(df_processed.columns):,}")
    col3.metric("Duplicates removed", f"{duplicates_removed:,}")

    if duplicates_removed > 0:
        st.info(
            f"ℹ️ {duplicates_removed:,} exact duplicate row(s) were removed. "
            "Details will appear in the data cleaning report."
        )

    if currency_value != "N/A":
        st.caption(f"Detected currency: **{currency_value}**")

    # -----------------------------------------------------------------------
    # Company Name (необязательное поле) — Section 14
    # Используется для брендинга PDF/Excel отчётов и filename
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader("📝 Company Information (Optional)")
    st.caption(
        "Add your company name to personalize reports. "
        "This will appear on PDF/Excel exports and in filenames."
    )

    company_name_input = st.text_input(
        "Company or Business Name",
        value=st.session_state.get("company_name", {}).get("display_name", ""),
        placeholder="e.g., Acme Corp",
        help="Optional. Leave empty if you prefer generic reports.",
        key="company_name_input",
    )

    # Сохраняем в session_state (Section 14: company_name dict)
    if company_name_input.strip():
        # Очищаем для filename: только буквы, цифры, дефисы, подчёркивания
        import re
        filename_safe = re.sub(r'[^\w\s-]', '', company_name_input).strip()
        filename_safe = re.sub(r'[-\s]+', '_', filename_safe).lower()

        st.session_state["company_name"] = {
            "display_name": company_name_input.strip(),
            "filename_safe_name": filename_safe or "report",
        }
    else:
        # Пустое значение — используем дефолт
        st.session_state["company_name"] = {
            "display_name": "",
            "filename_safe_name": "report",
        }

    # -----------------------------------------------------------------------
    # Предпросмотр данных
    # -----------------------------------------------------------------------
    with st.expander("Preview data (first 10 rows)", expanded=False):
        st.dataframe(df_processed.head(10), use_container_width=True)

    # -----------------------------------------------------------------------
    # Навигация к следующему шагу (Section 16: Step 1 → Step 2 = 3_mapping.py)
    # -----------------------------------------------------------------------
    render_cta_button(
        title="✅ File Uploaded Successfully!",
        subtitle="Map your file columns to SubAudit fields",
        button_label="▶ Continue to Column Mapping",
        target_page="pages/3_mapping.py",
        button_key="continue_to_mapping_btn",
    )


# ---------------------------------------------------------------------------
# Запуск
# ---------------------------------------------------------------------------
# Streamlit запускает страницу как скрипт — main() вызывается напрямую.
# "or True" убран намеренно: он вызывал main() при любом импорте модуля (баг).
main()
