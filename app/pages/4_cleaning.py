"""
app/pages/4_cleaning.py
SubAudit — Страница очистки данных
Реализована строго по Master Specification Sheet v2.9, Section 16 Step 3.
Использует: core/cleaner.py (clean_data), Section 3, Section 4, Section 14.
"""

import streamlit as st
import threading
import time

# ---------------------------------------------------------------------------
# Импорт внутренних модулей (согласно Section 4 — Project File Structure)
# ---------------------------------------------------------------------------
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.cleaner import clean_data
from app.core.mapper import apply_mapping
from app.observability.logger import log_error, log_warning, log_info
from app.utils.page_setup import inject_nav_css, render_sidebar, record_activity

# ---------------------------------------------------------------------------
# set_page_config — ПЕРВЫЙ вызов Streamlit, до любых st.* (Section 16 Step 3)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SubAudit — Data Cleaning",
    page_icon="🧹",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------
CLEANING_TIMEOUT_SECONDS = 30  # Таймаут для threading.Timer (Section 16 Step 3)

# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _check_session_prerequisites() -> bool:
    """
    Проверяет, что необходимые данные сессии присутствуют.
    Согласно Section 14: df_clean ещё не создан на этом этапе,
    поэтому проверяем наличие column_mapping (результат Step 2 / 3_mapping.py).
    Все сообщения для пользователя — на английском.
    """
    if "column_mapping" not in st.session_state:
        st.error(
            "⚠️ Column mapping not found. "
            "Please go back to the upload step and start again."
        )
        st.page_link("pages/2_upload.py", label="← Back to Upload")
        return False

    # df_raw должен присутствовать — он ещё не удалён (удаляем ПОСЛЕ clean_data)
    if "df_raw" not in st.session_state:
        st.error(
            "⚠️ Source data not found in session. "
            "Your session may have expired — please upload your file again."
        )
        st.page_link("pages/2_upload.py", label="← Back to Upload")
        return False

    return True


def _run_cleaning_with_timeout(df_raw, column_mapping: dict) -> dict | None:
    """
    Запускает clean_data() с защитой через threading.Timer.
    Section 16 Step 3: threading.Timer timeout обязателен для 4_cleaning.py.
    Section 18 (Known Limitations): фоновый поток продолжает работу после таймаута
    (~30–60 MB доп. памяти при 2 параллельных таймаутах) — принятый риск v1.

    Возвращает словарь {'df_clean': ..., 'cleaning_report': ...} или None при таймауте.
    """
    result_container: dict = {}
    error_container: dict = {}
    timed_out_flag: dict = {"value": False}

    def _target():
        """Целевая функция для потока очистки."""
        try:
            # Применяем маппинг колонок перед очисткой (Section 16 Step 2→3)
            df_mapped = apply_mapping(df_raw, column_mapping)
            df_clean, cleaning_report = clean_data(df_mapped)
            if not timed_out_flag["value"]:
                result_container["df_clean"] = df_clean
                result_container["cleaning_report"] = cleaning_report
        except Exception as exc:  # noqa: BLE001
            if not timed_out_flag["value"]:
                error_container["exc"] = exc

    def _on_timeout():
        """Вызывается threading.Timer по истечении таймаута."""
        timed_out_flag["value"] = True

    # Запускаем поток очистки
    worker = threading.Thread(target=_target, daemon=True)
    timer = threading.Timer(CLEANING_TIMEOUT_SECONDS, _on_timeout)

    timer.start()
    worker.start()
    worker.join(timeout=CLEANING_TIMEOUT_SECONDS + 1)  # Небольшой запас
    timer.cancel()  # Отменяем таймер, если поток завершился раньше

    # Проверяем результаты
    if timed_out_flag["value"]:
        log_warning(
            "clean_data() timed out",
            extra={"timeout_seconds": CLEANING_TIMEOUT_SECONDS},
        )
        return None

    if "exc" in error_container:
        raise error_container["exc"]

    if result_container:
        return result_container

    # Поток завершился, но результата нет — нештатная ситуация
    log_warning("clean_data() finished without result and without exception")
    return None


def _display_cleaning_report(cleaning_report: dict) -> None:
    """
    Отображает отчёт об очистке данных.
    Поля отчёта определены в Section 3 (Data Limits & Validation).
    Все тексты на английском — пользователь видит этот экран.
    """
    st.subheader("📋 Data Cleaning Report")

    col1, col2, col3 = st.columns(3)

    with col1:
        duplicates = cleaning_report.get("duplicates_removed", 0)
        st.metric(
            label="Duplicates removed",
            value=duplicates,
            help="Exact duplicate rows were removed (Section 3: Duplicate rows).",
        )

    with col2:
        zeros_excluded = cleaning_report.get("zeros_excluded", 0)
        st.metric(
            label="Rows with amount = 0",
            value=zeros_excluded,
            help=(
                "Rows with amount == 0 are excluded from MRR calculations "
                "but kept in the cleaned dataset (Section 3: Amount == 0)."
            ),
        )

    with col3:
        negatives_excluded = cleaning_report.get("negatives_excluded", 0)
        st.metric(
            label="Refund rows (amount < 0)",
            value=negatives_excluded,
            help=(
                "Rows with amount < 0 are counted as revenue churn (refunds) "
                "and excluded from MRR (Section 3: Amount < 0)."
            ),
        )

    # Дополнительные поля отчёта, если cleaner их возвращает
    extra_keys = {k: v for k, v in cleaning_report.items()
                  if k not in ("duplicates_removed", "zeros_excluded", "negatives_excluded")}
    if extra_keys:
        with st.expander("Cleaning details"):
            for key, value in extra_keys.items():
                st.write(f"**{key}**: {value}")


# ---------------------------------------------------------------------------
# Основная функция страницы
# ---------------------------------------------------------------------------

def main() -> None:
    """Точка входа страницы 4_cleaning.py."""

    # Скрываем автонавигацию, показываем сайдбар (Section 4)
    inject_nav_css()
    render_sidebar()

    # Явное действие пользователя — обновляем last_activity (Section 14)
    record_activity()

    # Заголовок и описание — на английском (пользователь видит)
    st.title("🧹 Data Cleaning")
    st.write(
        "Your file is being automatically cleaned and prepared for analysis. "
        "The result will be used to calculate all metrics."
    )

    # ------------------------------------------------------------------
    # Проверка предусловий сессии (Section 14: Session State & Memory)
    # ------------------------------------------------------------------
    if not _check_session_prerequisites():
        st.stop()

    # ------------------------------------------------------------------
    # Если df_clean уже вычислен — показываем результат без повторной очистки
    # ------------------------------------------------------------------
    if "df_clean" in st.session_state and "cleaning_report" in st.session_state:
        st.success("✅ Data already cleaned. Loaded from your current session.")
        _display_cleaning_report(st.session_state["cleaning_report"])

        # Информация о df_clean — на английском
        df_clean = st.session_state["df_clean"]
        st.info(
            f"Cleaned dataset: **{len(df_clean):,}** rows, "
            f"**{df_clean.shape[1]}** columns."
        )

        st.page_link("pages/5_dashboard.py", label="Go to Dashboard →")
        return

    # ------------------------------------------------------------------
    # Запуск очистки данных
    # ------------------------------------------------------------------
    df_raw = st.session_state["df_raw"]
    column_mapping = st.session_state["column_mapping"]

    # Информация о входных данных — на английском
    st.info(
        f"Rows to process: **{len(df_raw):,}**. "
        f"Starting cleaning (timeout: {CLEANING_TIMEOUT_SECONDS}s)…"
    )

    with st.spinner("Cleaning data… please wait."):
        start_time = time.monotonic()
        try:
            result = _run_cleaning_with_timeout(df_raw, column_mapping)
        except Exception as exc:
            # Необработанное исключение из clean_data()
            log_error(f"Error during data cleaning: {exc}")
            st.error(
                f"❌ An error occurred during data cleaning: {exc}\n\n"
                "Please check your file and try again."
            )
            st.page_link("pages/2_upload.py", label="← Upload a different file")
            st.stop()

        elapsed = time.monotonic() - start_time

    # ------------------------------------------------------------------
    # Обработка таймаута (Section 16 Step 3: threading.Timer timeout)
    # Сообщение об ошибке — на английском
    # ------------------------------------------------------------------
    if result is None:
        st.error(
            f"❌ Data cleaning took longer than {CLEANING_TIMEOUT_SECONDS} seconds and was stopped. "
            "Your file may be too large or contain unexpected data patterns. "
            "Try reducing the file size or uploading a different file."
        )
        st.page_link("pages/2_upload.py", label="← Upload a different file")
        st.stop()

    # ------------------------------------------------------------------
    # Сохранение результатов в session_state
    # Section 14: df_clean — pd.DataFrame; pop df_raw immediately after df_clean created
    # ------------------------------------------------------------------
    df_clean = result["df_clean"]
    cleaning_report = result["cleaning_report"]

    st.session_state["df_clean"] = df_clean
    st.session_state["cleaning_report"] = cleaning_report

    # Section 14: pop df_raw immediately after df_clean created
    st.session_state.pop("df_raw", None)
    log_info(
        "Cleaning complete, df_raw removed from session_state",
        extra={"elapsed_seconds": round(elapsed, 2), "rows_clean": len(df_clean)},
    )

    # ------------------------------------------------------------------
    # Отображение результатов — все тексты на английском
    # ------------------------------------------------------------------
    st.success(
        f"✅ Cleaning completed in {elapsed:.1f}s. "
        f"Cleaned dataset: **{len(df_clean):,}** rows."
    )

    _display_cleaning_report(cleaning_report)

    # Предпросмотр очищенных данных — заголовок на английском
    with st.expander("🔍 Preview cleaned data (first 50 rows)"):
        st.dataframe(df_clean.head(50), use_container_width=True)

    st.divider()

    # Кнопка перехода к дашборду — на английском
    st.page_link("pages/5_dashboard.py", label="Go to Dashboard →")


# ---------------------------------------------------------------------------
# Запуск страницы
# ---------------------------------------------------------------------------
main()
