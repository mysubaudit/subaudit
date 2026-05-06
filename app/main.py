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
# CSS — скрываем автонавигацию Streamlit (глобально для всего приложения)
# ---------------------------------------------------------------------------

# ВАЖНО: Streamlit Community Cloud автоматически показывает ВСЕ файлы из
# папки /pages/ в боковой панели. Это поведение нельзя отключить штатными
# средствами. Решение — скрыть через CSS и заменить на контролируемую
# навигацию через st.page_link() в _render_sidebar_nav().
_HIDE_STREAMLIT_AUTONAV_CSS = """
<style>
    /* Скрываем автогенерируемый список страниц Streamlit */
    [data-testid="stSidebarNav"] {
        display: none !important;
    }

    /* Скрываем верхний декоративный блок над навигацией */
    [data-testid="stSidebarNavItems"] {
        display: none !important;
    }

    /* Убираем отступ, который Streamlit оставляет под скрытой навигацией */
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 1rem;
    }
</style>
"""


def _inject_global_css() -> None:
    """
    Внедряет глобальные CSS-стили сразу после set_page_config.
    Вызывается один раз в начале каждого рендера.
    Скрывает автогенерируемую навигацию Streamlit (stSidebarNav).
    """
    st.markdown(_HIDE_STREAMLIT_AUTONAV_CSS, unsafe_allow_html=True)


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
      - пользователю показывается информационное сообщение (на английском — для пользователей)
      - st.stop() прерывает дальнейший рендер страницы
    """
    now: float = time.time()

    # --- Guard 1: максимальный возраст сессии ---
    session_age: float = now - st.session_state.get("session_start", now)
    if session_age > MAX_AGE_SECONDS:
        _clear_session()
        # Текст на английском — аудитория англоязычная (Section 1 проекта)
        st.info(
            "Your session has expired (maximum session length is 8 hours). "
            "Please upload your file again to continue."
        )
        st.stop()

    # --- Guard 2: тайм-аут простоя ---
    idle_time: float = now - st.session_state.get("last_activity", now)
    if idle_time > IDLE_TIMEOUT_SECONDS:
        _clear_session()
        # Текст на английском — аудитория англоязычная
        st.info(
            "Your session ended due to inactivity (30 minutes). "
            "Please upload your file again to continue."
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
# Конфигурация страницы
# ---------------------------------------------------------------------------

def _configure_page() -> None:
    """
    Устанавливает глобальные параметры Streamlit-страницы.

    layout="wide" выбран для корректного отображения таблиц когорт и
    дашборда с метриками (Section 5–6, Section 7).

    initial_sidebar_state:
      - "collapsed" когда нет данных и пользователь не авторизован
        (новый посетитель видит чистый лендинг)
      - "expanded" когда пользователь работает с данными или авторизован
    """
    has_data: bool = st.session_state.get("df_clean") is not None
    user_logged_in: bool = bool(st.session_state.get("user_email"))

    # Новый незарегистрированный пользователь — скрываем сайдбар полностью
    sidebar_state = "expanded" if (has_data or user_logged_in) else "collapsed"

    st.set_page_config(
        page_title="SubAudit — Subscription Analytics",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state=sidebar_state,
    )


# ---------------------------------------------------------------------------
# Сайдбар — контролируемая навигация (заменяет автонавигацию Streamlit)
# ---------------------------------------------------------------------------

def _render_sidebar_nav() -> None:
    """
    Отображает навигационную боковую панель с контролируемым набором ссылок.

    ЛОГИКА ОТОБРАЖЕНИЯ СТРАНИЦ (что видит пользователь в зависимости от состояния):

    Состояние 1 — Новый пользователь (не залогинен, нет данных):
        → Сайдбар не показывается вообще.
          Пользователь видит только лендинг. Навигация не нужна.

    Состояние 2 — Пользователь загрузил файл (не залогинен, есть данные):
        → Показываем: Upload (загрузить снова), Dashboard, Pricing, (Login через Account)
          Пользователь может работать с данными на FREE плане.

    Состояние 3 — Пользователь залогинен, нет данных:
        → Показываем: Upload, Pricing, Account
          Пользователь должен загрузить файл.

    Состояние 4 — Пользователь залогинен И есть данные:
        → Показываем все рабочие страницы: Upload, Dashboard, Pricing, Account

    ВАЖНО: Mapping (3) и Cleaning (4) не включены в навигацию намеренно —
    они вызываются автоматически через flow (Upload → Mapping → Cleaning → Dashboard).
    Прямой переход на эти страницы без контекста приведёт к ошибке.

    Все тексты — на английском (аудитория англоязычная).
    Комментарии — на русском (только для разработчика).
    """
    has_data: bool = st.session_state.get("df_clean") is not None
    user_email: str | None = st.session_state.get("user_email")
    user_logged_in: bool = bool(user_email)

    # Состояние 1: новый пользователь — сайдбар не нужен
    if not has_data and not user_logged_in:
        return

    with st.sidebar:
        # ── Логотип / заголовок ──────────────────────────────────────────
        st.markdown("## 📊 SubAudit")
        st.markdown("---")

        # ── Текущий план (Section 14: user_plan, Section 2: планы) ──────
        plan: str = st.session_state.get("user_plan", "free")
        plan_labels: dict[str, str] = {
            "free": "🆓 Free",
            "starter": "⭐ Starter",
            "pro": "🚀 Pro",
        }
        st.markdown(f"**Plan:** {plan_labels.get(plan, plan.capitalize())}")

        # ── Предупреждение подписки (Section 13) ────────────────────────
        if st.session_state.get("subscription_warning", False):
            reason: str = st.session_state.get(
                "subscription_warning_reason", "api_error"
            )
            if reason == "no_cache":
                st.warning("⚠️ Could not verify subscription. Free plan applied.")
            else:
                st.warning("⚠️ Subscription API error. Using cached plan.")

        st.markdown("---")

        # ── Навигационные ссылки (контролируемые, не авто-Streamlit) ────
        # st.page_link доступен в Streamlit >= 1.31 (у нас 1.35.0 — Section 15)

        # Upload — показываем всегда когда сайдбар виден
        st.page_link("pages/2_upload.py", label="📤 Upload Data", icon=None)

        # Dashboard — только если есть загруженные данные
        if has_data:
            st.page_link("pages/5_dashboard.py", label="📊 Dashboard", icon=None)

        # Pricing — всегда (пользователь должен иметь доступ к апгрейду)
        st.page_link("pages/6_pricing.py", label="💰 Pricing", icon=None)

        # Account — только если залогинен (иначе смысла нет)
        if user_logged_in:
            st.page_link("pages/7_account.py", label="👤 Account", icon=None)

        st.markdown("---")

        # ── Email пользователя (маскируем — PII, Section 7) ─────────────
        if user_email:
            masked: str = (
                user_email[:3] + "***@" + user_email.split("@")[-1]
                if "@" in user_email
                else "***"
            )
            st.caption(f"Signed in as: {masked}")

        st.caption("SubAudit v2.9")


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Главная функция — точка входа приложения SubAudit.

    Порядок вызовов строго соответствует Section 4 и Section 16, Step 1:

    1. Конфигурация страницы (должна быть ПЕРВЫМ вызовом Streamlit)
    2. Внедрение глобального CSS (скрываем автонавигацию Streamlit)
    3. Инициализация Sentry
    4. Инициализация session_state (при первом запуске)
    5. Session guards (проверка истечения сессии)
    6. Навигационная боковая панель (только при наличии данных или авторизации)
    7. Редирект на лендинг — main.py сам по себе не является страницей контента

    Маршрутизация по страницам выполняется самим Streamlit Community Cloud
    через механизм app/pages/*.py (Section 4).
    """
    # 1. Конфигурация страницы — ОБЯЗАТЕЛЬНО первый вызов st.*
    _configure_page()

    # 2. Глобальный CSS — сразу после page_config, до любого контента
    #    Скрывает автогенерируемую навигацию [data-testid="stSidebarNav"]
    _inject_global_css()

    # 3. Инициализация Sentry (Section 4, Section 7)
    _init_sentry()

    # 4. Инициализация session_state (Section 14)
    _init_session_state()

    # 5. Session guards (Section 14: session_start MAX AGE + last_activity idle)
    _enforce_session_guards()

    # 6. Боковая панель — только если есть данные или пользователь авторизован
    _render_sidebar_nav()

    # 7. Редирект на лендинг
    #    main.py — точка входа, не является полноценной страницей контента.
    #    Streamlit Community Cloud при открытии корневого URL показывает main.py.
    #    Полноценный лендинг — в app/pages/1_landing.py (Section 16, Step 1).
    st.switch_page("pages/1_landing.py")


# ---------------------------------------------------------------------------
# Запуск
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
