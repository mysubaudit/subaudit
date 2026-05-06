"""
app/pages/3_mapping.py
Страница сопоставления колонок CSV с внутренними полями SubAudit.

Development Order Step 2 (Section 16):
  core/mapper.py  +  3_mapping.py

Использует:
  - auto_map_columns()  (Section 4, mapper.py)
  - Session state guard (Section 14)
  - Обязательные / необязательные поля (Section 5, Section 3)
  - Навигация: upload (2) → mapping (3) → cleaning (4)
"""

from __future__ import annotations  # эта строка ОБЯЗАНА быть первой

import sys
import os
# Добавляем корень проекта в sys.path для корректных импортов
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st

from app.core.mapper import (
    ALL_FIELDS,
    OPTIONAL_FIELDS,
    REQUIRED_FIELDS,
    auto_map_columns,
)

# ---------------------------------------------------------------------------
# Константы страницы
# ---------------------------------------------------------------------------

# Метки для отображения внутренних полей в UI — на английском (пользователь видит)
FIELD_LABELS: dict[str, str] = {
    "customer_id": "Customer ID",
    "date":        "Date / Period",
    "status":      "Status",
    "amount":      "Amount",
    "currency":    "Currency (optional)",
}

# Подсказки по каждому полю (tooltip в selectbox) — на английском (пользователь видит при наведении)
FIELD_HELP: dict[str, str] = {
    "customer_id": (
        "Unique customer identifier. "
        "Used to calculate all retention metrics (Section 5)."
    ),
    "date": (
        "Billing date or period. "
        "Accepted formats: YYYY-MM or YYYY-MM-DD. "
        "Used to determine last_month / prev_month (Section 5)."
    ),
    "status": (
        "Subscription status. "
        "Accepted values: active, churned, trial (Section 3)."
    ),
    "amount": (
        "Payment amount. "
        "Zero amounts are excluded from MRR; negative amounts are treated as refunds (Section 3)."
    ),
    "currency": (
        "Currency code (e.g. USD, EUR). "
        "If your file contains multiple currencies, processing will be blocked (Section 3). "
        "This field is optional if all rows share a single currency."
    ),
}

# Placeholder для «не выбрано» в selectbox — на английском (пользователь видит)
NOT_SELECTED = "— not selected —"


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def _go_back_to_upload() -> None:
    """Перенаправляет пользователя на страницу загрузки."""
    st.switch_page("pages/2_upload.py")


def _go_to_cleaning() -> None:
    """Перенаправляет пользователя на страницу очистки данных."""
    st.switch_page("pages/4_cleaning.py")


def _validate_mapping(mapping: dict[str, str | None]) -> list[str]:
    """
    Проверяет, что все обязательные поля сопоставлены.
    Возвращает список ошибок (пустой список = всё ОК).
    Section 5: customer_id, date, status, amount — обязательны.
    Тексты ошибок на английском — пользователь их видит.
    """
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if not mapping.get(field):
            errors.append(
                f"**{FIELD_LABELS[field]}** is required — please select a column."
            )
    return errors


def _check_duplicate_selections(mapping: dict[str, str | None]) -> list[str]:
    """
    Проверяет, что одна и та же колонка CSV не сопоставлена двум разным полям.
    Игнорирует None-значения.
    Тексты ошибок на английском — пользователь их видит.
    """
    selected = [v for v in mapping.values() if v]
    duplicates = {v for v in selected if selected.count(v) > 1}
    if duplicates:
        return [
            f"Column **{col}** is mapped to more than one field — "
            "each column can only be used once."
            for col in duplicates
        ]
    return []


# ---------------------------------------------------------------------------
# Основная функция страницы
# ---------------------------------------------------------------------------


def render_mapping_page() -> None:
    """
    Отображает страницу сопоставления колонок.

    Шаги:
    1. Guard: проверяем наличие df_raw в session_state (Section 14).
    2. Вызываем auto_map_columns() для автоматического предложения.
    3. Показываем selectbox для каждого поля.
    4. Валидируем выбор.
    5. Сохраняем column_mapping в session_state и переходим к шагу 4.
    """

    # Заголовок и подпись — на английском (пользователь видит)
    st.title("🗂 Column Mapping")
    st.caption("Step 2 of 4")

    # ------------------------------------------------------------------
    # Guard: df_raw должен существовать в session_state (Section 14).
    # Если пользователь попал сюда без загруженного файла — отправляем назад.
    # ------------------------------------------------------------------
    if "df_raw" not in st.session_state or st.session_state["df_raw"] is None:
        st.error(
            "No data loaded. Please upload a CSV file first."
        )
        st.button(
            "← Back to Upload",
            on_click=_go_back_to_upload,
            type="primary",
        )
        return

    df_raw = st.session_state["df_raw"]

    # ------------------------------------------------------------------
    # Превью загруженных данных — заголовок expander на английском
    # ------------------------------------------------------------------
    with st.expander("📋 Preview uploaded file", expanded=False):
        st.dataframe(df_raw.head(5), use_container_width=True)
        st.caption(
            f"Total rows: **{len(df_raw):,}** · "
            f"Columns: **{len(df_raw.columns)}** · "
            f"Column names: {', '.join(df_raw.columns.tolist())}"
        )

    st.divider()

    # ------------------------------------------------------------------
    # Автоматическое предложение сопоставления (auto_map_columns)
    # Section 4: auto_map_columns() — rapidfuzz
    # ------------------------------------------------------------------

    # Инициализируем авто-маппинг только если он ещё не был выполнен
    # (не перезаписываем ручной выбор пользователя при ре-рендере)
    if "auto_mapping_done" not in st.session_state:
        suggested = auto_map_columns(df_raw)
        st.session_state["_suggested_mapping"] = suggested
        st.session_state["auto_mapping_done"] = True
    else:
        suggested = st.session_state.get("_suggested_mapping", {})

    # Список всех колонок CSV + «не выбрано»
    csv_columns = [NOT_SELECTED] + list(df_raw.columns)

    # ------------------------------------------------------------------
    # Отображаем UI для каждого поля — все тексты на английском
    # ------------------------------------------------------------------
    st.subheader("Match your file columns to SubAudit fields")
    st.info(
        "Fields marked 🔴 are required. Fields marked 🟡 are optional. "
        "SubAudit has suggested a mapping automatically — please review and adjust if needed.",
        icon="ℹ️",
    )

    # Текущий маппинг — будем строить из виджетов
    current_mapping: dict[str, str | None] = {}

    # Два столбца для более компактного отображения
    col_left, col_right = st.columns(2)

    for idx, field in enumerate(ALL_FIELDS):
        # Чередуем левую и правую колонку
        target_col = col_left if idx % 2 == 0 else col_right

        # Метка поля с признаком обязательности
        is_required = field in REQUIRED_FIELDS
        label_prefix = "🔴" if is_required else "🟡"
        label = f"{label_prefix} {FIELD_LABELS[field]}"

        # Определяем текущий default: ранее выбранный или авто-предложенный
        session_key = f"_mapping_select_{field}"
        if session_key in st.session_state:
            # Пользователь уже делал выбор в этой сессии — восстанавливаем
            default_value = st.session_state[session_key]
        else:
            # Первый рендер — используем предложение auto_map_columns
            default_value = suggested.get(field)

        # Вычисляем индекс для selectbox
        if default_value and default_value in csv_columns:
            default_index = csv_columns.index(default_value)
        else:
            default_index = 0  # «— not selected —»

        with target_col:
            selected = st.selectbox(
                label=label,
                options=csv_columns,
                index=default_index,
                key=session_key,
                help=FIELD_HELP[field],
            )

        # None если «не выбрано»
        current_mapping[field] = selected if selected != NOT_SELECTED else None

    st.divider()

    # ------------------------------------------------------------------
    # Информационная панель: сводка текущего выбора — заголовки на английском
    # ------------------------------------------------------------------
    with st.expander("🔍 Current mapping summary", expanded=False):
        summary_rows = []
        for field in ALL_FIELDS:
            mapped_col = current_mapping.get(field)
            status_icon = "✅" if mapped_col else ("⚠️" if field in OPTIONAL_FIELDS else "❌")
            summary_rows.append({
                "SubAudit Field":  FIELD_LABELS[field],
                "CSV Column":      mapped_col or "not selected",
                "Status":          status_icon,
            })
        import pandas as pd
        st.dataframe(
            pd.DataFrame(summary_rows),
            use_container_width=True,
            hide_index=True,
        )

    # ------------------------------------------------------------------
    # Кнопка подтверждения + валидация — текст на английском
    # ------------------------------------------------------------------
    confirm_clicked = st.button(
        "Confirm mapping →",
        type="primary",
        use_container_width=True,
    )

    if confirm_clicked:
        # Валидация обязательных полей
        errors = _validate_mapping(current_mapping)
        # Проверка дублирования колонок
        errors += _check_duplicate_selections(current_mapping)

        if errors:
            for err in errors:
                st.error(err)
        else:
            # ----------------------------------------------------------
            # Сохраняем column_mapping в session_state (Section 14)
            # Ключ: 'column_mapping' — dict с сопоставлением полей.
            # None-значения для необязательных полей (currency) допустимы.
            # ----------------------------------------------------------
            st.session_state["column_mapping"] = current_mapping

            # Сбрасываем флаг авто-маппинга, чтобы при возврате
            # снова предлагать авто-предложение на свежих данных
            if "auto_mapping_done" in st.session_state:
                del st.session_state["auto_mapping_done"]
            if "_suggested_mapping" in st.session_state:
                del st.session_state["_suggested_mapping"]

            # Сообщение об успехе — на английском
            st.success("Mapping saved. Proceeding to data cleaning...")
            _go_to_cleaning()

    # ------------------------------------------------------------------
    # Кнопка «Назад» — на английском
    # ------------------------------------------------------------------
    st.button(
        "← Upload a different file",
        on_click=_go_back_to_upload,
        use_container_width=True,
    )


# ---------------------------------------------------------------------------
# Точка входа страницы Streamlit
# page_title на английском — отображается во вкладке браузера (пользователь видит)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="SubAudit — Column Mapping",
    page_icon="🗂",
    layout="wide",
)

st.markdown("""
<style>
[data-testid="stSidebarNav"] { display: none !important; }
[data-testid="stSidebarNavItems"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

render_mapping_page()
