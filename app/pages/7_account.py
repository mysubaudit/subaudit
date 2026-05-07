"""
7_account.py — Страница аккаунта пользователя SubAudit
Реализовано строго по Master Specification Sheet v2.9.
Используемые разделы: Section 4, 11, 12, 13, 14, 16 (Step 6).

Комментарии — на русском (только для разработчика).
Весь текст, который видит пользователь — на английском (англоязычная аудитория).
"""

import time
import streamlit as st
from datetime import date

# Импортируем вспомогательные модули согласно Section 4
from app.auth.supabase_auth import send_magic_link, get_user_plan, keep_alive_if_needed
from app.payments.lemon_squeezy import get_subscription_status
from app.observability.logger import log_info, log_warning

# ─────────────────────────────────────────────────────────────────────────────
# Константа кулдауна для повторной отправки magic link
# Section 11 / Section 12: COOLDOWN = 60 seconds
# ─────────────────────────────────────────────────────────────────────────────
COOLDOWN = 60  # секунды — НЕ связано с логикой keepalive (Section 11)


def _require_login() -> bool:
    """
    Проверяем, авторизован ли пользователь.
    Если нет — показываем заглушку и останавливаем выполнение.
    Section 14: user_email хранится в session_state.
    Текст на английском — пользователь видит этот экран.
    """
    if not st.session_state.get("user_email"):
        st.warning("You are not signed in. Please log in using a magic link.")
        st.stop()
        return False
    return True


def _get_seconds_since_last_sent() -> float | None:
    """
    Вычисляем, сколько секунд прошло с момента последней отправки magic link.
    Section 14: magic_link_last_sent — float (Unix timestamp).
    Возвращает None, если ссылка ещё не отправлялась.
    """
    last_sent = st.session_state.get("magic_link_last_sent")
    if last_sent is None:
        return None
    return time.time() - last_sent


def _render_plan_badge(plan: str) -> None:
    """
    Отображаем бейдж текущего тарифного плана.
    Section 2: возможные значения — 'free', 'starter', 'pro'.
    Тексты на английском — пользователь видит.
    """
    plan_labels = {
        "free":    "🆓 FREE",
        "starter": "⭐ STARTER — $19/mo",
        "pro":     "🚀 PRO — $49/mo",
    }
    label = plan_labels.get(plan, "❓ Unknown plan")
    st.markdown(f"### Current plan: **{label}**")


def _render_subscription_warning() -> None:
    """
    Показываем предупреждение, если проверка подписки завершилась с ошибкой.
    Section 13: subscription_warning, subscription_warning_reason.
    Тексты на английском — пользователь видит этот экран.
    """
    if st.session_state.get("subscription_warning"):
        reason = st.session_state.get("subscription_warning_reason", "")
        if reason == "no_cache":
            st.warning(
                "⚠️ Could not verify your subscription status. "
                "Free plan is applied by default. "
                "If you recently upgraded — please wait up to 60 seconds and refresh the page."
            )
        elif reason == "api_error":
            st.warning(
                "⚠️ Subscription API error. "
                "Your cached plan is being used. "
                "If this issue persists, please contact support."
            )


def _refresh_subscription(user_email: str) -> str:
    """
    Перепроверяем план через Lemon Squeezy.
    Section 13: всегда показываем st.spinner, таймаут 5s, Checkpoint 1/3.
    Section 2: план ДОЛЖЕН быть перепроверён перед PDF/Excel экспортом.
    Здесь — обновление по запросу пользователя.
    """
    # Section 13: st.spinner уже внутри get_subscription_status() — двойная обёртка убрана
    plan = get_subscription_status(user_email)
    # Обновляем план в session_state (Section 14)
    st.session_state["user_plan"] = plan
    log_info(f"[7_account] Subscription refreshed for {user_email}: {plan}")
    return plan


def _render_magic_link_resend(user_email: str) -> None:
    """
    Блок повторной отправки magic link с кулдауном 60 секунд.
    Section 11 / Section 12: COOLDOWN = 60 секунд.
    Section 14: magic_link_last_sent — float Unix timestamp.
    Кулдаун НЕ связан с логикой keep_alive_if_needed (Section 11).
    Тексты на английском — пользователь видит этот блок.
    """
    st.subheader("Re-send login link")

    seconds_since = _get_seconds_since_last_sent()

    if seconds_since is not None and seconds_since < COOLDOWN:
        # Кулдаун ещё не истёк — показываем оставшееся время
        remaining = int(COOLDOWN - seconds_since)
        st.info(
            f"⏳ You can re-send in {remaining} second(s). "
            f"(Cooldown: {COOLDOWN}s)"
        )
        # Кнопка заблокирована во время кулдауна
        st.button(
            "Send magic link",
            disabled=True,
            help=f"Please wait {remaining} second(s) before re-sending.",
        )
    else:
        # Кулдаун истёк или ссылка ещё не отправлялась
        if st.button("Send magic link"):
            success = send_magic_link(user_email)
            if success:
                # Записываем Unix timestamp момента отправки (Section 14)
                st.session_state["magic_link_last_sent"] = time.time()
                st.success(
                    f"✅ Magic link sent to {user_email}. "
                    "Please check your inbox."
                )
                log_info(f"[7_account] Magic link sent: {user_email}")
            else:
                st.error(
                    "❌ Failed to send magic link. "
                    "Please try again later or contact support."
                )
                log_warning(f"[7_account] Failed to send magic link: {user_email}")


def _render_account_info(user_email: str, plan: str) -> None:
    """
    Отображаем основную информацию об аккаунте.
    Section 14: user_email, user_plan из session_state.
    Section 2: описание возможностей по планам.
    Все тексты на английском — пользователь видит этот экран.
    """
    st.subheader("Account information")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Email:** {user_email}")
    with col2:
        _render_plan_badge(plan)

    # Краткое описание возможностей текущего плана (Section 2)
    plan_features = {
        "free": [
            "Up to 1,000 rows",
            "1 CSV file per session",
            "Basic metrics (Blocks 1–2)",
            "PDF export with watermark",
            "No forecast or simulation",
        ],
        "starter": [
            "Up to 10,000 rows",
            "1 CSV file per session",
            "All 5 metric blocks",
            "PDF export — no watermark",
            "Excel export with formulas",
            "Forecast: realistic ≥ 3 mo; all 3 scenarios ≥ 6 mo",
        ],
        "pro": [
            "Up to 50,000 rows",
            "1 CSV file per session",
            "All 5 metric blocks",
            "PDF export — branded (company name)",
            "Excel export with formulas",
            "Forecast: all 3 scenarios ≥ 6 mo",
            "Simulation dashboard + PDF export",
        ],
    }

    features = plan_features.get(plan, [])
    if features:
        st.markdown("**Your plan includes:**")
        for feature in features:
            st.markdown(f"- {feature}")


def _render_manage_subscription(plan: str) -> None:
    """
    Кнопка перехода в Lemon Squeezy Customer Portal для управления подпиской.
    Показывается только платным пользователям (starter / pro).
    TODO: заменить CUSTOMER_PORTAL_URL на реальный URL после одобрения Lemon Squeezy.
    Текст на английском — пользователь видит этот блок.
    """
    if plan not in ("starter", "pro"):
        return

    # TODO: после одобрения Lemon Squeezy вставить реальный Customer Portal URL сюда
    CUSTOMER_PORTAL_URL = "#"  # заглушка — заменить на реальный URL

    st.divider()
    st.markdown("### ⚙️ Manage Subscription")
    st.markdown(
        "You can cancel, pause, or change your plan directly "
        "in the billing portal."
    )

    if CUSTOMER_PORTAL_URL == "#":
        # Заглушка — портал ещё не настроен
        st.info(
            "🔧 Subscription management portal is coming soon. "
            "To make changes, email us at "
            "[biz.sardorbek@gmail.com](mailto:biz.sardorbek@gmail.com)."
        )
    else:
        # Реальная кнопка — откроется после получения URL от Lemon Squeezy
        st.link_button(
            "Open Billing Portal",
            url=CUSTOMER_PORTAL_URL,
            type="primary",
        )


def _render_feedback_section() -> None:
    """
    Секция обратной связи — оценка, сообщение, ссылка на email.
    Используем st.feedback() (доступен в Streamlit >= 1.35.0 — Section 15).
    Данные НЕ отправляются автоматически — пользователь кликает mailto ссылку.
    Текст на английском — пользователь видит этот блок.
    """
    st.divider()
    st.markdown("### 💬 Share Your Feedback")
    st.markdown(
        "We'd love to hear what you think — "
        "ratings, suggestions, bug reports, or just a hello. 👋"
    )

    # Звёздочный рейтинг — встроенный виджет Streamlit 1.35 (Section 15)
    rating = st.feedback("stars", key="user_feedback_stars")

    # Текстовое поле для развёрнутого сообщения
    message = st.text_area(
        "Your message (optional)",
        placeholder="Tell us what you love, what's missing, or what could be better...",
        max_chars=1000,
        key="user_feedback_message",
    )

    # Формируем mailto ссылку с предзаполненным телом письма
    # Пользователь кликает — открывается его почтовый клиент с готовым письмом
    stars_text = ""
    if rating is not None:
        # rating возвращает 0-4 (индекс), переводим в 1-5 звёзд
        stars_count = rating + 1
        stars_text = f"Rating: {'⭐' * stars_count} ({stars_count}/5)%0A"

    msg_text = message.replace("\n", "%0A").replace(" ", "%20") if message else ""
    subject = "SubAudit%20Feedback"
    body = f"{stars_text}{msg_text}"

    st.markdown(
        f"[📧 Send feedback to biz.sardorbek@gmail.com]"
        f"(mailto:biz.sardorbek@gmail.com?subject={subject}&body={body})",
    )
    st.caption(
        "Clicking the link opens your email client with your message pre-filled."
    )


def _render_upgrade_cta(plan: str) -> None:
    """
    CTA для апгрейда плана — показываем, если план не PRO.
    Section 4: 6_pricing.py — страница сравнения планов.
    Тексты на английском — пользователь видит.
    """
    if plan != "pro":
        st.divider()
        st.markdown("### 🚀 Want more features?")
        st.markdown(
            "Upgrade to **STARTER** or **PRO** to unlock advanced metrics, "
            "forecasting, and simulation."
        )
        if st.button("Compare plans and upgrade"):
            # Переходим на страницу pricing (Section 4: 6_pricing.py)
            st.switch_page("pages/6_pricing.py")


def _render_logout() -> None:
    """
    Кнопка выхода из аккаунта.
    Очищаем пользовательские ключи session_state (Section 14).
    Тексты на английском — пользователь видит.
    """
    st.divider()
    if st.button("🚪 Sign out"):
        # Удаляем пользовательские данные из session_state (Section 14)
        keys_to_clear = [
            "user_email",
            "user_plan",
            "magic_link_last_sent",
            "last_keepalive_date",
            "subscription_warning",
            "subscription_warning_reason",
            # Данные сессии тоже сбрасываем
            "df_clean",
            "column_mapping",
            "cleaning_report",
            "metrics_dict",
            "data_quality_flags",
            "forecast_dict",
            "simulation_dict",
            "company_name",
            "currency",
            # Дебаунс-флаги экспорта сбрасываем при выходе (Section 14)
            "pdf_generating",
            "excel_generating",
        ]
        for key in keys_to_clear:
            st.session_state.pop(key, None)

        st.success("You have been signed out.")
        log_info("[7_account] User signed out.")
        # Перенаправляем на landing (Section 4: 1_landing.py)
        st.switch_page("pages/1_landing.py")


# ─────────────────────────────────────────────────────────────────────────────
# Основная точка входа страницы
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """
    Точка входа для страницы 7_account.py.
    Section 16 Step 6 — страница аккаунта с кулдауном magic link.
    """
    st.set_page_config(
        page_title="SubAudit — Account",
        page_icon="👤",
        layout="centered",
    )
    st.markdown("""
    <style>
    [data-testid="stSidebarNav"] { display: none !important; }
    [data-testid="stSidebarNavItems"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

    st.title("👤 Account")

    # Проверяем авторизацию (Section 14: user_email)
    _require_login()

    user_email: str = st.session_state["user_email"]

    # Отображаем предупреждение подписки, если есть (Section 13)
    _render_subscription_warning()

    # Получаем актуальный план из session_state (Section 14)
    plan: str = st.session_state.get("user_plan", "free")

    # Информация об аккаунте и план (Section 2, Section 14)
    _render_account_info(user_email, plan)

    st.divider()

    # Кнопка ручного обновления статуса подписки (Section 13)
    if st.button("🔄 Refresh subscription status"):
        plan = _refresh_subscription(user_email)
        st.rerun()

    # Section 13: post-upgrade delay — показываем если предупреждение сработало
    # сразу после апгрейда (пользователь мог только что оплатить)
    if st.session_state.get("subscription_warning") and plan == "free":
        st.info(
            "💡 If you just upgraded — payment processors may take up to 60 seconds. "
            "Please refresh the page in a moment."
        )

    st.divider()

    # Блок повторной отправки magic link с кулдауном (Section 11, Section 12)
    # COOLDOWN = 60 секунд — строго по спецификации
    _render_magic_link_resend(user_email)

    # CTA апгрейда, если план не PRO (Section 4: 6_pricing.py)
    _render_upgrade_cta(plan)

    # Управление подпиской — только для платных планов
    _render_manage_subscription(plan)

    # Форма обратной связи — для всех авторизованных пользователей
    _render_feedback_section()

    # Кнопка выхода (Section 14)
    _render_logout()


if __name__ == "__main__":
    main()
