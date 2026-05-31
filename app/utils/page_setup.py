"""
app/utils/page_setup.py
Общие UI-утилиты для всех страниц SubAudit.

Назначение:
  - inject_nav_css()  — скрывает автонавигацию Streamlit (stSidebarNav)
  - render_sidebar()  — управляемый сайдбар (только нужные пользователю страницы)
  - record_activity() — обновление last_activity (Section 14)

Почему нужен этот модуль:
  Streamlit запускает каждую страницу из /pages/ как отдельный скрипт.
  main.py НЕ выполняется при переходе на subpage. Значит CSS и сайдбар
  из main.py не работают на upload/dashboard/mapping/cleaning.
  Решение: каждая страница импортирует и вызывает функции из этого модуля.

Импорт в каждой странице:
    from app.utils.page_setup import inject_nav_css, render_sidebar, record_activity

Порядок вызовов (ОБЯЗАТЕЛЬНЫЙ):
    st.set_page_config(...)   ← первым, до любых st.* вызовов
    inject_nav_css()          ← сразу после set_page_config
    render_sidebar()          ← после inject_nav_css

Section 4 (File Structure) — вспомогательный модуль приложения.
Section 14 (Session State) — record_activity обновляет last_activity.
"""

import time
import streamlit as st

from app.auth.supabase_auth import send_magic_link

# ---------------------------------------------------------------------------
# Обработка отложенной навигации из CTA кнопок
# ---------------------------------------------------------------------------

def handle_cta_redirect():
    """
    Проверяет, есть ли отложенная навигация из CTA кнопок.
    Должна вызываться в начале каждой страницы после render_sidebar().
    """
    if "_cta_target" in st.session_state:
        target = st.session_state.pop("_cta_target")
        st.switch_page(target)

# ---------------------------------------------------------------------------
# CSS — скрытие автонавигации Streamlit
# ---------------------------------------------------------------------------

# Streamlit Community Cloud автоматически показывает ВСЕ файлы из /pages/
# в сайдбаре через [data-testid="stSidebarNav"]. Отключить штатно нельзя.
# Скрываем через CSS и заменяем на контролируемую навигацию (render_sidebar).
_NAV_CSS = """
<style>
    /* Скрываем автогенерируемый список страниц (ВСЕГДА) */
    * [data-testid="stSidebarNav"],
    [data-testid="stSidebar"] [data-testid="stSidebarNav"],
    [data-testid="stSidebarNav"],
    [data-testid="stSidebarNavItems"],
    [data-testid="stSidebar"] [data-testid="stSidebarNavItems"] {
        display: none !important;
        visibility: hidden !important;
        width: 0 !important;
        height: 0 !important;
        overflow: hidden !important;
    }

    /* Скрываем весь sidebar по умолчанию (без данных нет навигации) */
    section[data-testid="stSidebar"] {
        display: none !important;
        width: 0 !important;
        min-width: 0 !important;
        max-width: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        border: none !important;
        overflow: hidden !important;
        visibility: hidden !important;
        opacity: 0 !important;
    }

    /* Скрываем кнопку открытия/закрытия sidebar */
    button[data-testid="collapsedControl"] {
        display: none !important;
    }

    /* Показываем sidebar только если внутри есть контент */
    section[data-testid="stSidebar"]:has(.sidebar-content) {
        display: flex !important;
        width: auto !important;
        min-width: auto !important;
        max-width: none !important;
        overflow: visible !important;
    }
</style>
"""


def inject_nav_css() -> None:
    """
    Внедряет CSS, скрывающий автонавигацию Streamlit.
    Вызывать СРАЗУ после st.set_page_config(), до любого другого контента.

    На лендинге (1_landing.py) вызов не нужен — там весь sidebar скрыт через
    собственный CSS. На всех остальных страницах — обязателен.
    """
    st.markdown(_NAV_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Управляемый сайдбар
# ---------------------------------------------------------------------------

def render_sidebar() -> None:
    """
    Отображает сайдбар с контролируемым набором ссылок.

    Логика видимости страниц (что показываем пользователю):

    Состояние 1 — новый пользователь (не залогинен, нет данных):
        → ничего не показываем (пустой сайдбар уместнее навигации)

    Состояние 2 — загружен файл, пользователь не залогинен:
        → Upload (загрузить снова), Dashboard, Pricing

    Состояние 3 — залогинен, нет файла:
        → Upload, Pricing, Account

    Состояние 4 — залогинен + есть данные:
        → Upload, Dashboard, Pricing, Account

    ВАЖНО: Mapping (3_mapping.py) и Cleaning (4_cleaning.py) намеренно
    исключены из навигации — они вызываются автоматически через flow.
    Прямой переход без контекста приведёт к ошибке.

    Section 2: plan labels — free/starter/pro.
    Section 13: subscription_warning — отображаем в сайдбаре.
    Section 14: user_email, user_plan из session_state.
    Section 7 (PII): email маскируется перед показом.
    """
    has_data: bool = st.session_state.get("df_clean") is not None
    user_email: str | None = st.session_state.get("user_email")
    user_logged_in: bool = bool(user_email)

    # Состояние 1: новый незарегистрированный пользователь без данных —
    # сайдбар пустой, навигация не нужна
    if not has_data and not user_logged_in:
        return

    with st.sidebar:
        # Маркер для CSS — показывает что sidebar имеет контент
        st.markdown('<div class="sidebar-content">', unsafe_allow_html=True)

        # ── Логотип / заголовок ──────────────────────────────────────────────
        st.markdown("## 📊 SubAudit")
        st.markdown("---")

        # ── Текущий план (Section 14: user_plan; Section 2: планы) ──────────
        plan: str = st.session_state.get("user_plan", "free")
        plan_labels: dict[str, str] = {
            "free":    "🆓 Free",
            "starter": "⭐ Starter",
            "pro":     "🚀 Pro",
        }
        st.markdown(f"**Plan:** {plan_labels.get(plan, plan.capitalize())}")

        # ── Предупреждение подписки (Section 13) ────────────────────────────
        if st.session_state.get("subscription_warning", False):
            reason: str = st.session_state.get(
                "subscription_warning_reason", "api_error"
            )
            if reason == "no_cache":
                st.warning("⚠️ Could not verify subscription. Free plan applied.")
            else:
                st.warning("⚠️ Subscription API error. Using cached plan.")

        st.markdown("---")

        # ── Навигационные ссылки ─────────────────────────────────────────────
        # st.page_link доступен в Streamlit >= 1.31 (у нас 1.35.0 — Section 15)

        # Upload — показываем всегда когда сайдбар виден
        st.page_link("pages/2_upload.py", label="📤 Upload Data")

        # Dashboard — только если есть загруженные данные
        if has_data:
            st.page_link("pages/5_dashboard.py", label="📊 Dashboard")

        # Pricing — всегда (пользователь должен видеть возможность апгрейда)
        st.page_link("pages/6_pricing.py", label="💰 Pricing")

        # Help — всегда (пользователь может застрять на любом этапе)
        st.page_link("pages/8_help.py", label="❓ Help")

        # Account — только если залогинен
        if user_logged_in:
            st.page_link("pages/7_account.py", label="👤 Account")

        st.markdown("---")

        # ── Email (маскируем — PII, Section 7) ──────────────────────────────
        if user_email:
            masked: str = (
                user_email[:3] + "***@" + user_email.split("@")[-1]
                if "@" in user_email
                else "***"
            )
            st.caption(f"Signed in as: {masked}")

        st.caption("SubAudit v3.3")

        # Закрываем маркер контента
        st.markdown('</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Обновление метки активности
# ---------------------------------------------------------------------------

def record_activity() -> None:
    """
    Обновляет время последнего явного действия пользователя.

    Согласно Section 14: last_activity обновляется ТОЛЬКО при явных действиях
    (загрузка файла, подтверждение маппинга, запрос экспорта и т.п.).
    Простой рендер страницы — НЕ является активностью.

    Тест: test_render_does_not_reset_idle (Section 17) проверяет что рендер
    не вызывает обновление — поэтому вызывать эту функцию нужно явно,
    только внутри обработчиков действий.
    """
    st.session_state["last_activity"] = time.time()


# ---------------------------------------------------------------------------
# Free login gate — шаг 4a Free login fix
# Показывает login prompt для незалогиненных пользователей перед загрузкой.
# Не блокирует загрузку, но мотивирует залогиниться для сохранения snapshot.
# ---------------------------------------------------------------------------

def render_login_gate() -> None:
    """
    Показывает лёгкий login prompt для Free users без auth.

    Цель: конверсия Free → logged-in. Залогиненные Free users сохраняют snapshot
    (шаг 4b), что создаёт retention loop и превращает утилиту в SaaS.

    Не блокирует загрузку — показываем как nudge, не gate.
    """
    user_email: str | None = st.session_state.get("user_email")
    if user_email:
        return  # Уже залогинен — ничего не показываем

    user_plan: str = st.session_state.get("user_plan", "free")
    if user_plan != "free":
        return  # Платящие уже залогинены автоматически

    st.divider()
    st.info(
        "🔐 **Save your data forever** — just sign in with email. "
        "Upload without an account, but your data won't be saved between sessions."
    )

    email_input = st.text_input(
        "Email to sign in",
        placeholder="you@example.com",
        key="login_gate_email",
    )

    last_sent = st.session_state.get("magic_link_last_sent")
    seconds_since = time.time() - last_sent if last_sent else None

    COOLDOWN = 60

    if seconds_since is not None and seconds_since < COOLDOWN:
        remaining = int(COOLDOWN - seconds_since)
        st.caption(f"⏳ Wait {remaining}s before resend")
        st.button("Send magic link", disabled=True, key="login_gate_btn")
    else:
        if st.button("Send magic link", key="login_gate_btn"):
            if not email_input or "@" not in email_input:
                st.error("Please enter a valid email address.")
            else:
                if send_magic_link(email_input.strip()):
                    st.session_state["magic_link_last_sent"] = time.time()
                    st.success(
                        f"✅ Check your inbox at **{email_input.strip()}**. "
                        "Click the link to sign in and save your data."
                    )
                else:
                    st.error("Failed to send. Please try again.")
