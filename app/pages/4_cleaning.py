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
    """
    if "column_mapping" not in st.session_state:
        st.error(
            "⚠️ Маппинг колонок не найден. "
            "Пожалуйста, вернитесь к шагу загрузки файла."
        )
        st.page_link("pages/2_upload.py", label="← Вернуться к загрузке")
        return False

    # df_raw должен присутствовать — он ещё не удалён (удаляем ПОСЛЕ clean_data)
    if "df_raw" not in st.session_state:
        st.error(
            "⚠️ Исходные данные не найдены в сессии. "
            "Возможно, сессия истекла — загрузите файл заново."
        )
        st.page_link("pages/2_upload.py", label="← Вернуться к загрузке")
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
            "clean_data() превысила таймаут",
            extra={"timeout_seconds": CLEANING_TIMEOUT_SECONDS},
        )
        return None

    if "exc" in error_container:
        raise error_container["exc"]

    if result_container:
        return result_container

    # Поток завершился, но результата нет — нештатная ситуация
    log_warning("clean_data() завершилась без результата и без исключения")
    return None


def _display_cleaning_report(cleaning_report: dict) -> None:
    """
    Отображает отчёт об очистке данных.
    Поля отчёта определены в Section 3 (Data Limits & Validation).
    """
    st.subheader("📋 Отчёт об очистке данных")

    col1, col2, col3 = st.columns(3)

    with col1:
        duplicates = cleaning_report.get("duplicates_removed", 0)
        st.metric(
            label="Удалено дублей",
            value=duplicates,
            help="Удалены точные дубликаты строк (Section 3: Duplicate rows).",
        )

    with col2:
        zeros_excluded = cleaning_report.get("zeros_excluded", 0)
        st.metric(
            label="Строк с amount = 0",
            value=zeros_excluded,
            help=(
                "Строки с amount == 0 исключены из MRR, "
                "но сохранены в df_clean (Section 3: Amount == 0)."
            ),
        )

    with col3:
        negatives_excluded = cleaning_report.get("negatives_excluded", 0)
        st.metric(
            label="Строк с amount < 0 (рефанды)",
            value=negatives_excluded,
            help=(
                "Строки с amount < 0 учтены как revenue_churn (рефанды). "
                "Исключены из MRR (Section 3: Amount < 0)."
            ),
        )

    # Дополнительные поля отчёта, если cleaner их возвращает
    extra_keys = {k: v for k, v in cleaning_report.items()
                  if k not in ("duplicates_removed", "zeros_excluded", "negatives_excluded")}
    if extra_keys:
        with st.expander("Подробности очистки"):
            for key, value in extra_keys.items():
                st.write(f"**{key}**: {value}")


# ---------------------------------------------------------------------------
# Основная функция страницы
# ---------------------------------------------------------------------------

def main() -> None:
    """Точка входа страницы 4_cleaning.py."""

    st.title("🧹 Очистка данных")
    st.write(
        "На этом шаге выполняется автоматическая очистка загруженного файла. "
        "Результат будет использован для расчёта метрик."
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
        st.success("✅ Данные уже очищены. Результат загружен из текущей сессии.")
        _display_cleaning_report(st.session_state["cleaning_report"])

        # Информация о df_clean
        df_clean = st.session_state["df_clean"]
        st.info(
            f"Очищенный датасет: **{len(df_clean):,}** строк, "
            f"**{df_clean.shape[1]}** колонок."
        )

        st.page_link("pages/5_dashboard.py", label="Перейти к дашборду →")
        return

    # ------------------------------------------------------------------
    # Запуск очистки данных
    # ------------------------------------------------------------------
    df_raw = st.session_state["df_raw"]
    column_mapping = st.session_state["column_mapping"]

    # Информация о входных данных
    st.info(
        f"Загружено строк: **{len(df_raw):,}**. "
        f"Запускаем очистку (таймаут: {CLEANING_TIMEOUT_SECONDS} сек.)…"
    )

    with st.spinner("Очистка данных… пожалуйста, подождите."):
        start_time = time.monotonic()
        try:
            result = _run_cleaning_with_timeout(df_raw, column_mapping)
        except Exception as exc:
            # Необработанное исключение из clean_data()
            log_error(f"Ошибка при очистке данных: {exc}")
            st.error(
                f"❌ Произошла ошибка при очистке данных: {exc}\n\n"
                "Пожалуйста, проверьте корректность файла и попробуйте снова."
            )
            st.page_link("pages/2_upload.py", label="← Загрузить другой файл")
            st.stop()

        elapsed = time.monotonic() - start_time

    # ------------------------------------------------------------------
    # Обработка таймаута (Section 16 Step 3: threading.Timer timeout)
    # ------------------------------------------------------------------
    if result is None:
        st.error(
            f"❌ Очистка данных заняла более {CLEANING_TIMEOUT_SECONDS} секунд и была прервана. "
            "Возможно, файл слишком большой или содержит некорректные данные. "
            "Попробуйте уменьшить объём данных или загрузить другой файл."
        )
        st.page_link("pages/2_upload.py", label="← Загрузить другой файл")
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
        "Очистка завершена, df_raw удалён из session_state",
        extra={"elapsed_seconds": round(elapsed, 2), "rows_clean": len(df_clean)},
    )

    # ------------------------------------------------------------------
    # Отображение результатов
    # ------------------------------------------------------------------
    st.success(
        f"✅ Очистка завершена за {elapsed:.1f} сек. "
        f"Итого строк в очищенном датасете: **{len(df_clean):,}**."
    )

    _display_cleaning_report(cleaning_report)

    # Предпросмотр очищенных данных
    with st.expander("🔍 Предпросмотр очищенных данных (первые 50 строк)"):
        st.dataframe(df_clean.head(50), use_container_width=True)

    st.divider()

    # Кнопка перехода к дашборду
    st.page_link("pages/5_dashboard.py", label="Перейти к дашборду →")


# ---------------------------------------------------------------------------
# Запуск страницы
# ---------------------------------------------------------------------------
main()
