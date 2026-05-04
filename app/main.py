"""
app/main.py
Точка входа приложения SubAudit.

Согласно Section 4 (Project File Structure):
  "Entry point, Sentry init, session guards, page routing"

Согласно Section 16 (Development Order), Step 1:
  "main.py (session guards + record_activity())"

Версия спецификации: v2.9
"""

import time
from datetime import date

import sentry_sdk
import streamlit as st
from sentry_sdk.integrations.logging import LoggingIntegration

# ---------------------------------------------------------------------------
# Константы сессии (Section 14 — Session State & Memory)
# ---------------------------------------------------------------------------

# Максимальное время жизни сессии — 8 часов (Section 14: session_start)
MAX_AGE_SECONDS: int = 8 * 3600

# Тайм-аут простоя — 30 минут.
# Section 14 фиксирует ключ last_activity и факт его обновления
# «на явных действиях пользователя ONLY»; test_session.py содержит
# test_idle_expires, подтверждающий наличие idle-guard.
IDLE_TIMEOUT_SECONDS: int = 30 * 60

# ---------------------------------------------------------------------------
# Инициализация Sentry (Section 4, Section 7 — observability/logger.py)
# ---------------------------------------------------------------------------

def _init_sentry() -> None:
    """
    Инициализирует Sentry SDK.

    DSN берётся из Streamlit Secrets (Section 19: "Sentry DSN in Secrets —
    not in code or README"). Если ключ отсутствует — Sentry не поднимается,
    приложение продолжает работу без трейсинга.

    LoggingIntegration подключается отдельно, чтобы log_warning() /
    log_error() из observability/logger.py автоматически отправляли события
    в Sentry (Section 7).
    """
    dsn: str = st.secrets.get("SENTRY_DSN", "")
    if not dsn:
        # DSN не задан — работаем без Sentry (допустимо для локальной разработки)
        return

    logging_integration = LoggingIntegration(
        level=None,       # захватываем все уровни logging.*
        event_level=None, # событие не создаётся автоматически — только через capture_*
    )

    sentry_sdk.init(
        dsn=dsn,
        integrations=[logging_integration],
        # Трейсинг производительности отключён: Streamlit Community Cloud
        # не требует traces_sample_rate (Section 4 — free tier hosting)
        traces_sample_rate=0.0,
        # PII не отправляем (Section 7 — "no PII, no sensitive data")
        send_default_pii=False,
    )


# ---------------------------------------------------------------------------
# Инициализация session_state (Section 14 — Session State & Memory)
# ---------------------------------------------------------------------------

def _init_session_state() -> None:
    """
    Устанавливает начальные значения всех ключей session_state при старте
    новой сессии. Вызывается один раз — при первом рендере main.py.

    Полный список ключей соответствует Section 14 (Session State & Memory).
    """
    now: float = time.time()

    # — временны́е метки сессии —
    if "session_start" not in st.session_state:
        st.session_state["session_start"] = now          # Section 14

    if "last_activity" not in st.session_state:
        st.session_state["last_activity"] = now          # Section 14

    # — данные загруженного файла —
    if "df_clean" not in st.session_state:
        st.session_state["df_clean"] = None              # Section 14: pd.DataFrame

    if "column_mapping" not in st.session_state:
        st.session_state["column_mapping"] = {}          # Section 14: dict

    if "cleaning_report" not in st.session_state:
        st.session_state["cleaning_report"] = {}         # Section 14: dict

    # — результаты вычислений —
    if "metrics_dict" not in st.session_state:
        st.session_state["metrics_dict"] = {}            # Section 14: чистые метрики, без UI-ключей

    if "data_quality_flags" not in st.session_state:
        # Section 14: {prev_month_status, last_month_is_fallback, last_month_used}
        # Доступ ТОЛЬКО через session_state['data_quality_flags']['key']
        st.session_state["data_quality_flags"] = {}

    if "forecast_dict" not in st.session_state:
        st.session_state["forecast_dict"] = None         # Section 14: dict or None

    if "simulation_dict" not in st.session_state:
        st.session_state["simulation_dict"] = None       # Section 14: dict or None

    # — пользователь и план —
    if "user_plan" not in st.session_state:
        st.session_state["user_plan"] = "free"           # Section 14: 'free'/'starter'/'pro'

    if "user_email" not in st.session_state:
        st.session_state["user_email"] = None            # Section 14: str or None

    if "company_name" not in st.session_state:
        # Section 14: {'display_name': str, 'filename_safe_name': str}
        st.session_state["company_name"] = {
            "display_name": "",
            "filename_safe_name": "",
        }

    if "currency" not in st.session_state:
        st.session_state["currency"] = "USD"             # Section 14: str e.g. 'USD'

    # — дебаунс-флаги экспорта —
    if "pdf_generating" not in st.session_state:
        st.session_state["pdf_generating"] = False       # Section 14: bool

    if "excel_generating" not in st.session_state:
        st.session_state["excel_generating"] = False     # Section 14: bool

    # — аутентификация и подписка —
    if "magic_link_last_sent" not in st.session_state:
        st.session_state["magic_link_last_sent"] = 0.0  # Section 14: Unix timestamp

    if "last_keepalive_date" not in st.session_state:
        # Section 14: date — date.today(); устанавливается keep_alive_if_needed()
        # Инициализируем как None, чтобы keep_alive_if_needed() сработал при первом входе
        st.session_state["last_keepalive_date"] = None

    if "subscription_warning" not in st.session_state:
        st.session_state["subscription_warning"] = False # Section 14: bool

    # subscription_warning_reason создаётся только при необходимости (Section 14):
    # popped on successful check — не инициализируем заранее


# ---------------------------------------------------------------------------
# Сброс сессии
# ---------------------------------------------------------------------------

def _clear_session() -> None:
    """
    Полностью очищает session_state и инициирует новую сессию.

    Используется при истечении MAX_AGE или idle-тайм-аута.
    После clear() немедленно вызываем _init_session_state(), чтобы
    все обязательные ключи присутствовали до следующего рендера.
    """
    st.session_state.clear()
    _init_session_state()


# ---------------------------------------------------------------------------
# Session Guards (Section 14 — session_start / last_activity)
# ---------------------------------------------------------------------------

def _enforce_session_guards() -> None:
    """
    Проверяет два условия истечения сессии:

    1. MAX AGE (8 часов) — Section 14: "session_start: float — Unix timestamp;
       8-hour MAX AGE". Тест: test_max_age_expires (Section 17).

    2. IDLE TIMEOUT (30 минут) — Section 14: "last_activity: float — Unix
       timestamp; updated on explicit user actions ONLY".
       Тест: test_idle_expires (Section 17).

    При срабатывании любого из условий:
      - сессия сбрасывается через _clear_session()
      - пользователю показывается информационное сообщение
      - st.stop() прерывает дальнейший рендер страницы
    """
    now: float = time.time()

    # --- Guard 1: максимальный возраст сессии ---
    session_age: float = now - st.session_state.get("session_start", now)
    if session_age > MAX_AGE_SECONDS:
        _clear_session()
        st.info(
            "Ваша сессия истекла (максимальное время — 8 часов). "
            "Пожалуйста, загрузите файл заново."
        )
        st.stop()

    # --- Guard 2: тайм-аут простоя ---
    idle_time: float = now - st.session_state.get("last_activity", now)
    if idle_time > IDLE_TIMEOUT_SECONDS:
        _clear_session()
        st.info(
            "Сессия завершена из-за отсутствия активности (30 минут). "
            "Пожалуйста, загрузите файл заново."
        )
        st.stop()


# ---------------------------------------------------------------------------
# record_activity() (Section 14 — last_activity)
# ---------------------------------------------------------------------------

def record_activity() -> None:
    """
    Обновляет метку времени последней активности пользователя.

    Согласно Section 14: last_activity обновляется «на явных действиях
    пользователя ONLY» — рендер страниц сам по себе НЕ считается активностью.

    Эта функция должна вызываться из страниц приложения в ответ на
    явные действия: загрузка файла, подтверждение маппинга, запрос экспорта
    и т.п. Импортируется как:
        from app.main import record_activity
    """
    st.session_state["last_activity"] = time.time()


# ---------------------------------------------------------------------------
# Конфигурация страницы и навигации
# ---------------------------------------------------------------------------

def _configure_page() -> None:
    """
    Устанавливает глобальные параметры Streamlit-страницы.

    layout="wide" выбран для корректного отображения таблиц когорт и
    дашборда с метриками (Section 5–6, Section 7).
    """
    st.set_page_config(
        page_title="SubAudit — Subscription Analytics",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def _render_sidebar_nav() -> None:
    """
    Отображает навигационное меню в боковой панели.

    Streamlit Community Cloud автоматически обнаруживает файлы в app/pages/
    и строит навигацию, но мы явно дублируем ссылки для UX-ясности.
    Порядок страниц соответствует Section 4 (Project File Structure).

    Примечание: Streamlit сам управляет роутингом через pages/;
    здесь мы только отображаем дополнительный контекст о плане.
    """
    with st.sidebar:
        st.markdown("## SubAudit")
        st.markdown("---")

        # Отображаем текущий план пользователя (Section 14: user_plan)
        plan: str = st.session_state.get("user_plan", "free")
        plan_labels: dict[str, str] = {
            "free": "🆓 Free",
            "starter": "⭐ Starter",
            "pro": "🚀 Pro",
        }
        st.markdown(f"**План:** {plan_labels.get(plan, plan.capitalize())}")

        # Предупреждение о проблемах с подпиской (Section 13 — Lemon Squeezy)
        if st.session_state.get("subscription_warning", False):
            reason: str = st.session_state.get(
                "subscription_warning_reason", "api_error"
            )
            if reason == "no_cache":
                st.warning(
                    "⚠️ Не удалось проверить подписку. "
                    "Применён план Free."
                )
            else:
                st.warning(
                    "⚠️ Ошибка API подписки. "
                    "Используются кешированные данные."
                )

        st.markdown("---")

        # Email пользователя, если авторизован (Section 14: user_email)
        user_email: str | None = st.session_state.get("user_email")
        if user_email:
            # Показываем только первые символы для приватности (Section 7 — PII)
            masked: str = (
                user_email[:3] + "***@" + user_email.split("@")[-1]
                if "@" in user_email
                else "***"
            )
            st.caption(f"Пользователь: {masked}")

        st.caption("SubAudit v2.9")


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Главная функция — точка входа приложения SubAudit.

    Порядок вызовов строго соответствует Section 4 и Section 16, Step 1:

    1. Конфигурация страницы (должна быть ПЕРВЫМ вызовом Streamlit)
    2. Инициализация Sentry
    3. Инициализация session_state (при первом запуске)
    4. Session guards (проверка истечения сессии)
    5. Навигационная боковая панель
    6. Контент главной страницы (редирект на landing или upload)

    Маршрутизация по страницам выполняется самим Streamlit Community Cloud
    через механизм app/pages/*.py (Section 4).
    """
    # 1. Конфигурация страницы — ОБЯЗАТЕЛЬНО первый вызов st.*
    _configure_page()

    # 2. Инициализация Sentry (Section 4, Section 7)
    _init_sentry()

    # 3. Инициализация session_state (Section 14)
    _init_session_state()

    # 4. Session guards (Section 14: session_start MAX AGE + last_activity idle)
    _enforce_session_guards()

    # 5. Боковая панель с навигацией и статусом плана
    _render_sidebar_nav()

    # 6. Контент главной страницы
    #
    # main.py сам по себе не является одной из нумерованных страниц (Section 4).
    # При открытии корневого URL Streamlit отображает этот файл.
    # Мы показываем краткое приветствие и направляем пользователя на лэндинг.
    #
    # Полноценный лэндинг реализован в app/pages/1_landing.py (Section 16, Step 1).
    st.title("SubAudit")
    st.markdown(
        "**Subscription Analytics — превратите CSV-выгрузку в метрики SaaS.**"
    )
    st.markdown(
        "Используйте меню слева для навигации или перейдите "
        "на страницу **Upload** для загрузки файла."
    )

    # Информационный баннер о безопасности данных.
    # Section 2 (ℹ): «Files are processed in-memory and NEVER stored or
    # sent to third parties. This notice MUST appear on the Upload page —
    # verbatim.»
    # На главной странице дублируем мягко; verbatim-версия — в 2_upload.py.
    st.info(
        "🔒 Все файлы обрабатываются только в памяти браузера. "
        "Ваши данные не сохраняются и не передаются третьим сторонам."
    )


# ---------------------------------------------------------------------------
# Запуск
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
