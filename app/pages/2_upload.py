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
from app.utils.page_setup import inject_nav_css, render_sidebar, record_activity, render_login_gate
from app.utils.ui_components import render_cta_button
# v3.2.3: детектор формата CSV (SPEC.md §8)
from app.core.presets import detect_preset, build_preset_mapping

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
    st.caption(
        '← <a href="/1_landing" target="_self" style="color: #4F8EF7; text-decoration: none;">Back to Landing</a>',
        unsafe_allow_html=True,
    )

    # -----------------------------------------------------------------------
    # Inline help tooltip — что ожидать от этой страницы
    # -----------------------------------------------------------------------
    st.markdown("""
    Upload your CSV file with subscription data. We'll automatically detect the format and prepare it for analysis.

    **What you need:**
    - CSV file with customer transactions
    - At least 3 months of historical data (recommended: 6+ months)
    - Columns: Customer ID, Date, Amount, Status, Currency (optional)

    **Processing time:** ~5-30 seconds depending on file size.

    💡 **Tip:** Not sure about the format? Visit the [Help page](/8_help) to download a sample CSV.
    """)

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

    # 4a: Free login gate — login prompt для незалогиненных Free users
    render_login_gate()

    # -----------------------------------------------------------------------
    # Виджет загрузки файла — label меняется если файл уже загружен
    # Все label/help тексты на английском (пользователь видит эти тексты)
    # -----------------------------------------------------------------------
    file_uploader_label = (
        "Upload different file"
        if "df_raw" in st.session_state and st.session_state["df_raw"] is not None
        else "Choose a CSV file with your subscription data"
    )

    uploaded_file = st.file_uploader(
        label=file_uploader_label,
        type=["csv"],                   # Только .csv (Section 3)
        accept_multiple_files=False,    # Section 3: 1 файл на сессию
        help="Only .csv format is supported. Maximum file size is 15 MB.",
    )

    if uploaded_file is None:
        # Файл ещё не загружен — ждём
        st.stop()

    # -----------------------------------------------------------------------
    # ВАЖНО: Очищаем ВСЕ старые данные ПЕРЕД обработкой нового файла
    # Это гарантирует, что пользователь не увидит данные предыдущего файла
    # -----------------------------------------------------------------------
    keys_to_clear = [
        "df_raw", "df_clean", "column_mapping", "cleaning_report",
        "metrics_dict", "data_quality_flags", "forecast_dict",
        "simulation_dict", "currency", "company_name", "preset"
    ]
    for key in keys_to_clear:
        st.session_state.pop(key, None)

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

    # v3.3: сохраняем имя файла для source в snapshots
    st.session_state["source_file"] = file_name

        # v3.2.3: авто-определение формата CSV (SPEC.md §8)
    preset = detect_preset(df_processed, list(df_processed.columns))
    st.session_state["preset"] = preset

    # -------------------------------------------------------------------
    # v3.2.5: Авто-скип mapping при распознанном формате (SPEC.md §8)
    # Если пресет определён — показываем чекбокс "Auto-apply mapping"
    # (default ON). При включенном чекбоксе сразу сохраняем column_mapping
    # и отправляем пользователя на cleaning, пропуская 3_mapping.py.
    # -------------------------------------------------------------------
    if preset:
        preset_display = "LemonSqueezy" if preset == "lemonsqueezy" else preset.capitalize()

        auto_skip = st.checkbox(
            f"Auto-apply detected mapping ({preset_display} format)",
            value=True,
            help=(
                "When checked, column mapping will be applied automatically "
                "based on the detected format. Uncheck if you want to review "
                "or adjust mapping manually on the next page."
            ),
            key="auto_skip_mapping_checkbox",
        )

        if auto_skip:
            # ── Строим и сохраняем column_mapping из пресета ──
            column_mapping = build_preset_mapping(
                preset, list(df_processed.columns)
            )
            st.session_state["column_mapping"] = column_mapping

            # Успех — показываем сводку маппинга и кнопку на cleaning
            st.success(
                f"✅ {preset_display} format detected — "
                "mapping applied automatically."
            )

            # Сброс downstream-ключей (кроме column_mapping — он уже сохранён)
            for key in (
                "df_clean",
                "cleaning_report",
                "metrics_dict",
                "data_quality_flags",
                "forecast_dict",
                "simulation_dict",
                "currency",
            ):
                st.session_state.pop(key, None)

            # Сохраняем валюту
            currency_value = _get_currency_value(df_processed)
            st.session_state["currency"] = currency_value

            # Показываем auto-applied mapping в expander
            with st.expander("🔍 Auto-applied mapping", expanded=False):
                summary = []
                field_labels = {
                    "customer_id": "Customer ID",
                    "date": "Date",
                    "status": "Status",
                    "amount": "Amount",
                    "currency": "Currency",
                }
                for field, label in field_labels.items():
                    csv_col = column_mapping.get(field)
                    summary.append({
                        "Field": label,
                        "CSV Column": csv_col if csv_col else "—",
                    })
                st.dataframe(
                    pd.DataFrame(summary),
                    use_container_width=True,
                    hide_index=True,
                )

            # Навигация: пропускаем mapping → сразу cleaning
            render_cta_button(
                title="✅ Ready for Analysis!",
                subtitle="Mapping applied — proceed directly to data cleaning",
                button_label="▶ Continue to Data Cleaning",
                target_page="pages/4_cleaning.py",
                button_key="auto_skip_to_cleaning_btn",
            )
            st.stop()
    # Конец v3.2.5

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

    # v3.3.2: auto-save snapshot после upload (side effect, никогда не блокирует UI)
    if st.session_state.get("user_id") and not st.session_state.get("snapshot_saved", False):
        from datetime import datetime
        from app.core.snapshot import save_snapshot

        user_id = st.session_state["user_id"]
        period = datetime.utcnow().strftime("%Y-%m")
        source = file_name

        # Вычисляем метрики из df_processed (df_raw после дедупликации, до cleaning)
        from app.core.metrics import get_all_metrics  # noqa: F401
        metrics = get_all_metrics(df_processed)

        # Side effect — UI не зависит от успеха snapshot
        saved = save_snapshot(
            user_id=user_id,
            metrics=metrics,
            period=period,
            source=source,
        )
        if saved:
            st.session_state["snapshot_saved"] = True

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
