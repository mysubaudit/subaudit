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

import streamlit as st
import pandas as pd
from charset_normalizer import from_bytes  # Section 3: charset-normalizer (не chardet)
import io

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
    """
    # Шаг 1: Проба через charset-normalizer
    result = from_bytes(raw_bytes).best()
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
            raw_bytes.decode(enc)
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
        st.warning(
            "⚠️ Кодировка файла определена как latin-1 (последний вариант). "
            "Некоторые символы могут отображаться некорректно."
        )

    try:
        df = pd.read_csv(io.BytesIO(raw_bytes), encoding=encoding, low_memory=False)
        return df, ""
    except Exception as exc:
        return None, f"Не удалось прочитать CSV ({encoding}): {exc}"


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
        # Section 3: сначала предупреждение, потом усечение
        st.warning(
            f"⚠️ Файл содержит {actual:,} строк, но план «{user_plan.upper()}» "
            f"допускает не более {limit:,}. "
            f"Будут обработаны первые {limit:,} строк."
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
        return (
            f"❌ Файл содержит несколько валют: {currencies_list}. "
            "Смешивание валют не допускается. Пожалуйста, загрузите файл с одной валютой."
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
    """
    if "df_clean" not in st.session_state:
        st.info(
            "ℹ️ Сессия не содержит загруженных данных. "
            "Если вы обновили страницу или открыли новую вкладку — "
            "пожалуйста, загрузите CSV-файл снова. "
            "Данные хранятся только в памяти текущей сессии и не сохраняются на сервере."
        )


def main() -> None:
    """Точка входа страницы 2_upload.py."""

    st.set_page_config(
        page_title="SubAudit — Загрузка данных",
        page_icon="📂",
        layout="centered",
    )

    st.title("📂 Загрузка данных")

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

    st.caption(
        f"Ваш план: **{user_plan.upper()}** · "
        f"Максимум строк: **{limit_rows:,}** · "
        f"Максимальный размер файла: **15 МБ** · "
        f"Формат: **.csv**"
    )

    # -----------------------------------------------------------------------
    # Виджет загрузки файла — 1 файл на сессию (Section 3)
    # -----------------------------------------------------------------------
    uploaded_file = st.file_uploader(
        label="Выберите CSV-файл с данными подписок",
        type=["csv"],          # Только .csv (Section 3)
        accept_multiple_files=False,  # Section 3: 1 файл на сессию
        help="Поддерживается только формат .csv. Максимальный размер — 15 МБ.",
    )

    if uploaded_file is None:
        # Файл ещё не загружен
        st.stop()

    # -----------------------------------------------------------------------
    # Валидация расширения (Section 3: .csv only)
    # -----------------------------------------------------------------------
    file_name: str = uploaded_file.name
    if not file_name.lower().endswith(ALLOWED_EXTENSION):
        st.error(
            f"❌ Неподдерживаемый формат файла: «{file_name}». "
            "Допускается загрузка только файлов формата .csv."
        )
        st.stop()

    # -----------------------------------------------------------------------
    # Валидация размера файла (Section 3: 15 МБ)
    # -----------------------------------------------------------------------
    raw_bytes: bytes = uploaded_file.read()
    file_size_bytes: int = len(raw_bytes)

    if file_size_bytes > MAX_FILE_SIZE_BYTES:
        size_mb = file_size_bytes / (1024 * 1024)
        st.error(
            f"❌ Размер файла ({size_mb:.1f} МБ) превышает лимит 15 МБ. "
            "Пожалуйста, уменьшите файл и загрузите снова."
        )
        st.stop()

    # -----------------------------------------------------------------------
    # Чтение CSV с определением кодировки (Section 3)
    # -----------------------------------------------------------------------
    with st.spinner("Читаем файл..."):
        df_raw, read_error = _read_csv(raw_bytes)

    if df_raw is None:
        st.error(f"❌ Ошибка чтения файла: {read_error}")
        st.stop()

    if df_raw.empty:
        st.error("❌ Загруженный файл не содержит строк данных.")
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
    # Отчёт о базовой предобработке (informational)
    # Полный cleaning_report создаётся в core/cleaner.py (Step 3)
    # -----------------------------------------------------------------------
    st.success(f"✅ Файл «{file_name}» успешно загружен.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Строк загружено", f"{len(df_processed):,}")
    col2.metric("Столбцов", f"{len(df_processed.columns):,}")
    col3.metric("Удалено дубликатов", f"{duplicates_removed:,}")

    if duplicates_removed > 0:
        st.info(
            f"ℹ️ Удалено {duplicates_removed:,} точных дубликатов строк. "
            "Подробности будут отражены в отчёте о чистке данных."
        )

    if currency_value != "N/A":
        st.caption(f"Валюта данных: **{currency_value}**")

    # -----------------------------------------------------------------------
    # Предпросмотр данных
    # -----------------------------------------------------------------------
    with st.expander("Предпросмотр данных (первые 10 строк)", expanded=False):
        st.dataframe(df_processed.head(10), use_container_width=True)

    # -----------------------------------------------------------------------
    # Навигация к следующему шагу (Section 16: Step 1 → Step 2 = 3_mapping.py)
    # -----------------------------------------------------------------------
    st.divider()
    st.markdown("**Следующий шаг:** сопоставление столбцов файла с полями SubAudit.")

    if st.button("▶ Перейти к сопоставлению столбцов", type="primary", use_container_width=True):
        st.switch_page("pages/3_mapping.py")


# ---------------------------------------------------------------------------
# Запуск
# ---------------------------------------------------------------------------
if __name__ == "__main__" or True:
    main()
