"""
app/pages/6_pricing.py
SubAudit — Страница сравнения тарифов и апгрейда.
Строго по Master Specification Sheet v2.9, Section 2, 4, 16 (Step 6).

Комментарии — на русском (только для разработчика).
Весь текст, который видит пользователь — на английском (англоязычная аудитория).
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from app.utils.page_setup import inject_nav_css, render_sidebar

# ─────────────────────────────────────────────────────────────────────────────
# Конфигурация страницы
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SubAudit — Pricing",
    page_icon="💳",
    layout="wide",
)

# Скрываем автонавигацию Streamlit, показываем управляемый сайдбар
inject_nav_css()
render_sidebar()

# ─────────────────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────────────────────────────────────

def _get_current_plan() -> str:
    """
    Возвращает текущий план пользователя из session_state.
    Если пользователь не авторизован — возвращает 'free'.
    Section 14: user_plan хранится в session_state.
    """
    return st.session_state.get("user_plan", "free")


def _is_logged_in() -> bool:
    """
    Проверяет, авторизован ли пользователь.
    Section 14: user_email хранится в session_state.
    """
    return bool(st.session_state.get("user_email"))


def _render_subscription_warning() -> None:
    """
    Отображает предупреждение о проблеме с подпиской, если оно установлено.
    Section 13: subscription_warning + subscription_warning_reason.
    Тексты на английском — пользователь видит этот экран.
    """
    if st.session_state.get("subscription_warning"):
        reason = st.session_state.get("subscription_warning_reason", "")
        if reason == "no_cache":
            # Section 13: HTTP 401 или ошибка без кэша → показываем стандартное сообщение
            st.warning(
                "⚠️ Could not verify your subscription status. "
                "Free plan is applied by default. "
                "Payment processors may take up to 60 seconds — please refresh in a moment."
            )
        elif reason == "api_error":
            # Section 13: ошибка API, используется кэшированный план
            st.warning(
                "⚠️ Subscription API is temporarily unavailable. "
                "Your cached plan is being used. Status may not be current."
            )


# ─────────────────────────────────────────────────────────────────────────────
# Данные тарифных планов (Section 2 — Pricing Plans)
# Все строки для пользователя — на английском
# ─────────────────────────────────────────────────────────────────────────────

# Структура тарифов строго по Section 2 таблице Feature / FREE / STARTER / PRO
PLANS: list[dict] = [
    {
        "id": "free",
        "name": "FREE",
        "price": "$0",
        "price_sub": "forever",           # пользователь видит
        "login_required": False,
        "max_rows": "1,000",
        "csv_per_session": "1",
        "metric_blocks": "Basic (Blocks 1–2)",
        "pdf_export": "With watermark",
        "excel_export": "No",
        "forecast": "No",
        "simulation": "No",
        "cta_label": "Current plan",
        "cta_disabled": True,
        "highlight": False,
    },
    {
        "id": "starter",
        "name": "STARTER",
        "price": "$19",
        "price_sub": "/ month",           # пользователь видит
        "login_required": True,
        "max_rows": "10,000",
        "csv_per_session": "1",
        "metric_blocks": "All 5 blocks",
        "pdf_export": "No watermark",
        "excel_export": "Yes (with formulas)",
        "forecast": "Realistic ≥ 3 mo; all 3 scenarios ≥ 6 mo",
        "simulation": "No",
        "cta_label": "Get Starter",
        "cta_disabled": False,
        "highlight": False,
    },
    {
        "id": "pro",
        "name": "PRO",
        "price": "$49",
        "price_sub": "/ month",           # пользователь видит
        "login_required": True,
        "max_rows": "50,000",
        "csv_per_session": "1",
        "metric_blocks": "All 5 blocks",
        "pdf_export": "Branded (company name)",
        "excel_export": "Yes (with formulas)",
        "forecast": "Same as Starter",
        "simulation": "Dashboard + PDF export",
        "cta_label": "Get Pro",
        "cta_disabled": False,
        "highlight": True,  # PRO — выделенный план
    },
]

# Список строк таблицы сравнения — заголовки на английском (Section 2)
FEATURE_ROWS: list[tuple[str, str]] = [
    ("Login required",      "login_required"),
    ("Max rows",            "max_rows"),
    ("CSV files / session", "csv_per_session"),
    ("Metric blocks",       "metric_blocks"),
    ("PDF export",          "pdf_export"),
    ("Excel export",        "excel_export"),
    ("Forecast",            "forecast"),
    ("Simulation",          "simulation"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Рендер карточки тарифа
# ─────────────────────────────────────────────────────────────────────────────

def _render_plan_card(plan: dict, current_plan: str, is_logged_in: bool) -> None:
    """
    Рендерит карточку одного тарифа.
    CTA-кнопка ведёт на Gumroad (Section 13).
    Section 2: план FREE не требует авторизации, STARTER/PRO — требуют.
    Все тексты для пользователя — на английском.
    """
    plan_id = plan["id"]
    is_current = (plan_id == current_plan)

    # Заголовок и цена
    if plan["highlight"]:
        st.markdown(f"### ⭐ {plan['name']}")
    else:
        st.markdown(f"### {plan['name']}")

    st.markdown(
        f"<span style='font-size:2rem;font-weight:700'>{plan['price']}</span>"
        f"<span style='color:gray'> {plan['price_sub']}</span>",
        unsafe_allow_html=True,
    )

    st.divider()

    # Список ключевых возможностей плана
    for label, key in FEATURE_ROWS:
        value = plan[key]
        # Булевые значения превращаем в читаемые строки на английском
        if isinstance(value, bool):
            display = "✅ Yes" if value else "❌ No"
        else:
            # «No» стилизуем серым
            if value == "No":
                display = "<span style='color:gray'>—</span>"
            else:
                display = f"<strong>{value}</strong>"
        st.markdown(f"**{label}:** {display}", unsafe_allow_html=True)

    st.markdown("")  # отступ перед кнопкой

    # ── CTA-кнопка ──────────────────────────────────────────────────────────
    if is_current:
        # Текущий план пользователя — информационная плашка
        st.success("✅ Your current plan")

        # Кнопка управления подпиской — только для платных планов
        # TODO: заменить "#" на реальный Customer Portal URL Gumroad после получения
        if plan_id in ("starter", "pro"):
            CUSTOMER_PORTAL_URL = "#"  # заглушка — заменить после получения URL Gumroad
            if CUSTOMER_PORTAL_URL == "#":
                st.caption(
                    "To cancel or change your plan — email "
                    "[biz.sardorbek@gmail.com](mailto:biz.sardorbek@gmail.com)"
                )
            else:
                st.link_button(
                    "⚙️ Manage Subscription",
                    url=CUSTOMER_PORTAL_URL,
                    use_container_width=True,
                )

    elif plan_id == "free":
        # FREE всегда доступен без действий
        if not is_logged_in:
            st.info("You are on the free plan")
        else:
            # Авторизованный пользователь с платным планом — даунгрейд через v1 недоступен
            # Section 18: Downgrade not detected mid-session — принятое ограничение v1
            st.info("Free plan is available without a subscription")

    else:
        # STARTER и PRO — кнопка ведёт на Gumroad (Section 13)
        # Section 13: «Webhooks — None» — план обновляется на Checkpoint 1/2
        if not is_logged_in:
            # Section 2: STARTER/PRO требуют авторизации
            st.button(
                f"🔐 Sign in to get {plan['name']}",
                key=f"cta_{plan_id}_login",
                use_container_width=True,
                disabled=True,
            )
            st.caption("Please sign in via the Account page to subscribe.")
        else:
            # Авторизован — кнопка перехода на Gumroad checkout
            # URL берётся из st.secrets (Section 19: ключи только в Secrets UI)
            # Secrets: GUMROAD_CHECKOUT_STARTER, GUMROAD_CHECKOUT_PRO
            gumroad_defaults = {
                "starter": "https://subaudit.gumroad.com/l/starter",
                "pro":     "https://subaudit.gumroad.com/l/pro",
            }
            gumroad_url = st.secrets.get(
                f"GUMROAD_CHECKOUT_{plan_id.upper()}",
                gumroad_defaults[plan_id],
            )
            st.link_button(
                label=plan["cta_label"],
                url=gumroad_url,
                use_container_width=True,
            )
            st.caption(
                "After payment, return to the site — your plan will update automatically."
            )


# ─────────────────────────────────────────────────────────────────────────────
# Основной рендер страницы
# ─────────────────────────────────────────────────────────────────────────────

def render_pricing_page() -> None:
    """
    Главная функция рендера страницы тарифов.
    Section 4: файл app/pages/6_pricing.py — план сравнения и CTA.
    Section 16 Step 6: эта страница входит в 6-й шаг разработки.
    Все тексты для пользователя — на английском.
    """

    st.title("💳 SubAudit Plans")
    st.markdown(
        "Choose the plan that fits your business. "
        "All data is processed **in-memory** and never shared with third parties."
    )

    # Получаем текущий план и статус авторизации из session_state (Section 14)
    current_plan = _get_current_plan()
    is_logged_in = _is_logged_in()

    # Предупреждение о проблеме с подпиской (Section 13)
    _render_subscription_warning()

    # Информационная строка о текущем статусе пользователя
    if is_logged_in:
        plan_display = current_plan.upper()
        st.info(f"🔑 You are signed in. Current plan: **{plan_display}**")
    else:
        st.info(
            "You are not signed in. Free plan is active. "
            "Sign in via the **Account** page to access STARTER and PRO."
        )

    st.markdown("---")

    # ── Карточки планов (Section 2) ──────────────────────────────────────────
    cols = st.columns(3, gap="medium")
    for col, plan in zip(cols, PLANS):
        with col:
            _render_plan_card(plan, current_plan, is_logged_in)

    st.markdown("---")

    # ── Детальная таблица сравнения (Section 2 — полная таблица) ────────────
    st.subheader("📊 Full feature comparison")

    # Строим markdown-таблицу — заголовки и данные строго по Section 2
    header = "| Feature | FREE | STARTER ($19/mo) | PRO ($49/mo) |"
    divider_row = "|---|:---:|:---:|:---:|"

    rows = [header, divider_row]

    # Данные строк строго по Section 2
    table_data: list[tuple[str, str, str, str]] = [
        ("Login required",      "No",           "Yes",              "Yes"),
        ("Max rows",            "1,000",        "10,000",           "50,000"),
        ("CSV files / session", "1",            "1",                "1"),
        ("Metric blocks",       "Blocks 1–2",   "All 5",            "All 5"),
        ("PDF export",          "With watermark", "No watermark",   "Branded"),
        ("Excel export",        "—",            "✅ With formulas", "✅ With formulas"),
        ("Forecast",            "—",
         "Realistic ≥ 3 mo; all 3 scenarios ≥ 6 mo",
         "Same as Starter"),
        ("Simulation",          "—",            "—",                "✅ Dashboard + PDF"),
    ]

    for feat, free_val, starter_val, pro_val in table_data:
        rows.append(f"| {feat} | {free_val} | {starter_val} | {pro_val} |")

    st.markdown("\n".join(rows))

    st.markdown("---")

    # ── FAQ / известные ограничения (Section 18) ────────────────────────────
    # Все вопросы и ответы — на английском (пользователь видит)
    st.subheader("❓ Frequently asked questions")

    with st.expander("What happens when I refresh the browser?"):
        # Section 18: No persistent sessions across browser refresh
        st.markdown(
            "**Known limitation (v1):** Sessions are not preserved across browser refreshes. "
            "Refreshing the page will require you to log in again. "
            "Persistent sessions are planned for v3 (Supabase JWT cookies)."
        )

    with st.expander("How quickly does a plan change take effect?"):
        # Section 13: post-upgrade delay / Checkpoint логика
        st.markdown(
            "After payment via Gumroad, return to the site. "
            "Payment processors may take **up to 60 seconds** to process the transaction. "
            "If your plan hasn't updated — wait a moment and refresh the page. "
            "Your status is checked automatically on login and dashboard load."
        )

    with st.expander("Is my data stored on SubAudit servers?"):
        # Section 3 (ℹ notice) — VERBATIM из спецификации
        st.info(
            "Files are processed in-memory and NEVER stored or sent to third parties."
        )

    with st.expander("What is a plan downgrade?"):
        # Section 18: Downgrade not detected mid-session
        st.markdown(
            "A plan downgrade is only detected at the **next dashboard load in a new session**. "
            "Access within the current session is preserved. "
            "This is an accepted v1 limitation."
        )

    with st.expander("What does the PRO Simulation feature do?"):
        # Section 11: Simulation PRO only + ARPU homogeneity warning
        st.markdown(
            "The Simulation lets you model the impact of churn reduction, "
            "new customer growth, and price increases on your MRR over 12 months.\n\n"
            "⚠️ **Note:** Results assume uniform ARPU across all subscribers. "
            "With mixed pricing tiers, actual revenue impact may differ by 30–60%. "
            "Mixed-tier modelling is on the v2 roadmap."
        )

    st.markdown("---")

    # ── Навигационные кнопки — тексты на английском ──────────────────────────
    col_left, col_right = st.columns(2)
    with col_left:
        if st.button("← Back to Dashboard", use_container_width=True):
            st.switch_page("pages/5_dashboard.py")
    with col_right:
        if st.button("Go to Account →", use_container_width=True):
            st.switch_page("pages/7_account.py")

    # ── Контакт / обратная связь ─────────────────────────────────────────────
    # Короткая строка для вопросов — видна всем пользователям на странице тарифов
    st.markdown(
        "<div style='text-align:center; color:gray; margin-top:1rem;'>"
        "Questions about plans? Write to us: "
        "<a href='mailto:biz.sardorbek@gmail.com'>biz.sardorbek@gmail.com</a>"
        "</div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Точка входа
# ─────────────────────────────────────────────────────────────────────────────

render_pricing_page()
