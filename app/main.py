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

MAX_AGE_SECONDS: int = 8 * 3600
IDLE_TIMEOUT_SECONDS: int = 30 * 60

# ---------------------------------------------------------------------------
# CSS — скрываем автонавигацию Streamlit
# ---------------------------------------------------------------------------

_HIDE_STREAMLIT_AUTONAV_CSS = """
<style>
    [data-testid="stSidebarNav"] {
        display: none !important;
    }
    [data-testid="stSidebarNavItems"] {
        display: none !important;
    }
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 1rem;
    }
</style>
"""


def _inject_global_css() -> None:
    st.markdown(_HIDE_STREAMLIT_AUTONAV_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Инициализация Sentry
# ---------------------------------------------------------------------------

def _init_sentry() -> None:
    dsn: str = st.secrets.get("SENTRY_DSN", "")
    if not dsn:
        return

    logging_integration = LoggingIntegration(
        level=None,
        event_level=None,
    )

    sentry_sdk.init(
        dsn=dsn,
        integrations=[logging_integration],
        traces_sample_rate=0.0,
        send_default_pii=False,
    )


# ---------------------------------------------------------------------------
# Инициализация session_state (Section 14)
# ---------------------------------------------------------------------------

def _init_session_state() -> None:
    now: float = time.time()

    if "session_start" not in st.session_state:
        st.session_state["session_start"] = now

    if "last_activity" not in st.session_state:
        st.session_state["last_activity"] = now

    if "df_clean" not in st.session_state:
        st.session_state["df_clean"] = None

    if "column_mapping" not in st.session_state:
        st.session_state["column_mapping"] = {}

    if "cleaning_report" not in st.session_state:
        st.session_state["cleaning_report"] = {}

    if "metrics_dict" not in st.session_state:
        st.session_state["metrics_dict"] = {}

    if "data_quality_flags" not in st.session_state:
        st.session_state["data_quality_flags"] = {}

    if "forecast_dict" not in st.session_state:
        st.session_state["forecast_dict"] = None

    if "simulation_dict" not in st.session_state:
        st.session_state["simulation_dict"] = None

    if "user_plan" not in st.session_state:
        st.session_state["user_plan"] = "free"

    if "user_email" not in st.session_state:
        st.session_state["user_email"] = None

    if "company_name" not in st.session_state:
        st.session_state["company_name"] = {
            "display_name": "",
            "filename_safe_name": "",
        }

    if "currency" not in st.session_state:
        st.session_state["currency"] = "USD"

    if "pdf_generating" not in st.session_state:
        st.session_state["pdf_generating"] = False

    if "excel_generating" not in st.session_state:
        st.session_state["excel_generating"] = False

    if "magic_link_last_sent" not in st.session_state:
        st.session_state["magic_link_last_sent"] = 0.0

    if "last_keepalive_date" not in st.session_state:
        st.session_state["last_keepalive_date"] = None

    if "subscription_warning" not in st.session_state:
        st.session_state["subscription_warning"] = False

    # Причина предупреждения о подписке (Section 14: 'no_cache' | 'api_error')
    # Удаляется при успешной проверке — pop() в payments/gumroad.py
    if "subscription_warning_reason" not in st.session_state:
        st.session_state["subscription_warning_reason"] = ""


# ---------------------------------------------------------------------------
# Сброс сессии
# ---------------------------------------------------------------------------

def _clear_session() -> None:
    st.session_state.clear()
    _init_session_state()


# ---------------------------------------------------------------------------
# Session Guards (Section 14)
# ---------------------------------------------------------------------------

def _enforce_session_guards() -> None:
    now: float = time.time()

    session_age: float = now - st.session_state.get("session_start", now)
    if session_age > MAX_AGE_SECONDS:
        _clear_session()
        st.info(
            "Your session has expired (maximum session length is 8 hours). "
            "Please upload your file again to continue."
        )
        st.stop()

    idle_time: float = now - st.session_state.get("last_activity", now)
    if idle_time > IDLE_TIMEOUT_SECONDS:
        _clear_session()
        st.info(
            "Your session ended due to inactivity (30 minutes). "
            "Please upload your file again to continue."
        )
        st.stop()


# ---------------------------------------------------------------------------
# record_activity() (Section 14)
# ---------------------------------------------------------------------------

def record_activity() -> None:
    """
    Обновляет метку времени последней активности пользователя.
    Вызывать только на явных действиях пользователя (Section 14).
    """
    st.session_state["last_activity"] = time.time()


# ---------------------------------------------------------------------------
# Конфигурация страницы
# ---------------------------------------------------------------------------

def _configure_page() -> None:
    has_data: bool = st.session_state.get("df_clean") is not None
    user_logged_in: bool = bool(st.session_state.get("user_email"))
    sidebar_state = "expanded" if (has_data or user_logged_in) else "collapsed"

    st.set_page_config(
        page_title="SubAudit — Subscription Analytics",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state=sidebar_state,
    )


# ---------------------------------------------------------------------------
# Сайдбар
# ---------------------------------------------------------------------------

def _render_sidebar_nav() -> None:
    has_data: bool = st.session_state.get("df_clean") is not None
    user_email: str | None = st.session_state.get("user_email")
    user_logged_in: bool = bool(user_email)

    if not has_data and not user_logged_in:
        return

    with st.sidebar:
        st.markdown("## 📊 SubAudit")
        st.markdown("---")

        plan: str = st.session_state.get("user_plan", "free")
        plan_labels: dict[str, str] = {
            "free": "🆓 Free",
            "starter": "⭐ Starter",
            "pro": "🚀 Pro",
        }
        st.markdown(f"**Plan:** {plan_labels.get(plan, plan.capitalize())}")

        if st.session_state.get("subscription_warning", False):
            reason: str = st.session_state.get(
                "subscription_warning_reason", "api_error"
            )
            if reason == "no_cache":
                st.warning("⚠️ Could not verify subscription. Free plan applied.")
            else:
                st.warning("⚠️ Subscription API error. Using cached plan.")

        st.markdown("---")

        st.page_link("pages/2_upload.py", label="📤 Upload Data", icon=None)

        if has_data:
            st.page_link("pages/5_dashboard.py", label="📊 Dashboard", icon=None)

        st.page_link("pages/6_pricing.py", label="💰 Pricing", icon=None)

        if user_logged_in:
            st.page_link("pages/7_account.py", label="👤 Account", icon=None)

        st.markdown("---")

        if user_email:
            masked: str = (
                user_email[:3] + "***@" + user_email.split("@")[-1]
                if "@" in user_email
                else "***"
            )
            st.caption(f"Signed in as: {masked}")

        # Управление подпиской — Gumroad Customer Portal
        if user_logged_in and plan in ("starter", "pro"):
            st.markdown(
                "[⚙️ Manage Subscription](#)",  # TODO: заменить # на реальный Customer Portal URL Gumroad
                unsafe_allow_html=False,
            )
            st.markdown("---")

        st.markdown("**Questions or feedback?**")
        st.markdown(
            "📧 [biz.sardorbek@gmail.com](mailto:biz.sardorbek@gmail.com)",
            unsafe_allow_html=False,
        )
        st.markdown("---")

        st.caption("SubAudit v1.0")


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

def main() -> None:
    _configure_page()
    _inject_global_css()
    _init_sentry()
    _init_session_state()
    _enforce_session_guards()
    _render_sidebar_nav()
    st.switch_page("pages/1_landing.py")


if __name__ == "__main__":
    main()
