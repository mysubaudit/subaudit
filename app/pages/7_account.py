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
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Импортируем вспомогательные модули согласно Section 4
from app.auth.supabase_auth import send_magic_link, get_user_plan, keep_alive_if_needed
from app.payments.gumroad import get_subscription_status
from app.observability.logger import log_info, log_warning
from app.utils.page_setup import inject_nav_css, render_sidebar

# ─────────────────────────────────────────────────────────────────────────────
# Константа кулдауна для повторной отправки magic link
# Section 11 / Section 12: COOLDOWN = 60 seconds
# ─────────────────────────────────────────────────────────────────────────────
COOLDOWN = 60  # секунды — НЕ связано с логикой keepalive (Section 11)


def _require_login() -> bool:
    """
    Проверяем, авторизован ли пользователь.
    Если нет — показываем полную форму входа (email + кнопка "Send magic link")
    с кулдауном COOLDOWN=60 секунд (Section 11, Section 12).
    После отправки ссылки останавливаем рендер страницы через st.stop().
    Section 14: user_email и magic_link_last_sent хранятся в session_state.
    Текст на английском — пользователь видит этот экран.
    """
    if st.session_state.get("user_email"):
        return True  # Пользователь уже авторизован — продолжаем рендер

    # ── Форма входа ──────────────────────────────────────────────────────────
    st.info("🔐 Sign in to access your account. We'll send you a magic link — no password needed.")

    email_input = st.text_input(
        "Your email address",
        placeholder="you@example.com",
        key="login_email_input",
    )

    # Вычисляем, сколько секунд прошло с последней отправки (Section 14)
    seconds_since = None
    last_sent = st.session_state.get("magic_link_last_sent")
    if last_sent is not None:
        seconds_since = time.time() - last_sent

    # Кулдаун ещё не истёк — блокируем кнопку и показываем таймер (Section 11)
    if seconds_since is not None and seconds_since < COOLDOWN:
        remaining = int(COOLDOWN - seconds_since)
        st.info(f"⏳ You can re-send in {remaining} second(s). (Cooldown: {COOLDOWN}s)")
        st.button(
            "Send magic link",
            disabled=True,
            help=f"Please wait {remaining} second(s) before re-sending.",
            key="login_send_btn",
        )
    else:
        # Кулдаун истёк или ссылка ещё не отправлялась
        if st.button("Send magic link", key="login_send_btn"):
            if not email_input or "@" not in email_input:
                st.error("❌ Please enter a valid email address.")
            else:
                success = send_magic_link(email_input.strip())
                if success:
                    # Фиксируем время отправки — Unix timestamp (Section 14)
                    st.session_state["magic_link_last_sent"] = time.time()
                    st.success(
                        f"✅ Magic link sent to **{email_input.strip()}**. "
                        "Please check your inbox and click the link to sign in."
                    )
                    log_info(f"[7_account] Magic link sent from login form: {email_input.strip()}")
                else:
                    st.error(
                        "❌ Failed to send magic link. "
                        "Please try again later or contact support."
                    )
                    log_warning(f"[7_account] Failed to send magic link from login form: {email_input.strip()}")

    # Останавливаем рендер — остальная часть страницы не показывается
    # до тех пор, пока пользователь не авторизован (Section 14: user_email)
    st.stop()
    return False


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
    Перепроверяем план через Gumroad.
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
    Блок управления подпиской — ссылка на Gumroad для платных пользователей.
    Показывается только платным пользователям (starter / pro).
    Текст на английском — пользователь видит этот блок.
    """
    if plan not in ("starter", "pro"):
        return

    st.divider()
    st.markdown("### ⚙️ Manage Subscription")
    st.markdown(
        "To cancel or change your plan, visit your Gumroad purchase page "
        "or contact us directly."
    )
    st.info(
        "🔧 To manage your subscription, email us at "
        "[biz.sardorbek@gmail.com](mailto:biz.sardorbek@gmail.com) "
        "with your registered email address."
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

    # Инициализируем счётчик для сброса формы
    if "feedback_form_key" not in st.session_state:
        st.session_state["feedback_form_key"] = 0

    # Звёздочный рейтинг — встроенный виджет Streamlit 1.31+ (Section 15)
    # Проверяем доступность st.feedback (может отсутствовать в старых версиях)
    rating = None
    if hasattr(st, "feedback"):
        rating = st.feedback("stars", key=f"user_feedback_stars_{st.session_state['feedback_form_key']}")
    else:
        # Fallback для старых версий Streamlit
        rating_select = st.selectbox(
            "Rating (optional)",
            options=["", "⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"],
            key=f"user_feedback_stars_fallback_{st.session_state['feedback_form_key']}",
        )
        if rating_select:
            rating = len(rating_select) - 1  # Конвертируем в индекс 0-4

    # Текстовое поле для развёрнутого сообщения
    message = st.text_area(
        "Your message (optional)",
        placeholder="Tell us what you love, what's missing, or what could be better...",
        max_chars=1000,
        key=f"user_feedback_message_{st.session_state['feedback_form_key']}",
    )

    # Показываем сообщение об успешной отправке (если есть флаг)
    if st.session_state.get("feedback_sent"):
        st.success("✅ Thank you for your feedback! We appreciate it.")
        # Сбрасываем флаг
        st.session_state["feedback_sent"] = False

    # Кнопка отправки — сохраняет отзыв в Supabase
    if st.button("📤 Send Feedback", type="primary", use_container_width=True):
        # Проверка авторизации — отзыв могут оставить только залогиненные пользователи
        user_email = st.session_state.get("user_email")
        if not user_email:
            st.warning("⚠️ Please log in to send feedback.")
        # Валидация: хотя бы рейтинг или сообщение должны быть заполнены
        elif rating is None and not message.strip():
            st.warning("⚠️ Please provide a rating or message before sending.")
        else:
            # Импортируем функцию отправки отзыва
            from app.core.feedback import send_feedback

            # Конвертируем rating из индекса 0-4 в значение 1-5
            rating_value = (rating + 1) if rating is not None else None

            # Отправляем отзыв
            success = send_feedback(user_email, rating_value, message)

            if success:
                # Устанавливаем флаг успешной отправки
                st.session_state["feedback_sent"] = True
                # Инкрементируем счётчик для сброса формы
                st.session_state["feedback_form_key"] += 1
                st.rerun()
            else:
                st.error(
                    "❌ Failed to send feedback. Please try again or email us at "
                    "biz.sardorbek@gmail.com"
                )

    # История отзывов пользователя
    st.divider()
    st.markdown("### 📋 Your Feedback History")

    from app.core.feedback import get_user_feedback_history

    user_email = st.session_state.get("user_email")
    if user_email:
        feedback_history = get_user_feedback_history(user_email)

        if feedback_history:
            # Показываем последние 5 отзывов по умолчанию
            show_all = st.session_state.get("show_all_feedback", False)
            display_count = len(feedback_history) if show_all else min(5, len(feedback_history))

            for idx, item in enumerate(feedback_history[:display_count], 1):
                with st.expander(f"Feedback #{idx} — {item.get('created_at', 'N/A')[:10]}"):
                    # Рейтинг
                    if item.get("rating"):
                        st.markdown(f"**Rating:** {'⭐' * item['rating']}")

                    # Сообщение
                    if item.get("message"):
                        st.markdown(f"**Message:**")
                        st.text(item["message"])

                    # Дата
                    st.caption(f"Sent on: {item.get('created_at', 'N/A')}")

            # Кнопка "Show more" если отзывов больше 5
            if len(feedback_history) > 5 and not show_all:
                if st.button(f"Show all {len(feedback_history)} feedback items"):
                    st.session_state["show_all_feedback"] = True
                    st.rerun()
            elif show_all:
                if st.button("Show less"):
                    st.session_state["show_all_feedback"] = False
                    st.rerun()
        else:
            st.info("You haven't sent any feedback yet. Share your thoughts above! 👆")
    else:
        st.warning("Please log in to view your feedback history.")


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

    # Скрываем автонавигацию Streamlit, показываем управляемый сайдбар
    inject_nav_css()
    render_sidebar()

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

    # Section 13: post-upgrade delay — показываем если предупреждение сработало
    # сразу после апгрейда (пользователь мог только что оплатить)
    if st.session_state.get("subscription_warning") and plan == "free":
        st.warning(
            "⚠️ **Just completed payment?** Payment processors may take up to 60 seconds to sync. "
            "Click the button below to check your subscription status."
        )

    # Кнопка ручного обновления статуса подписки (Section 13)
    # Делаем её более заметной с type="primary" и полной шириной
    if st.button("🔄 Refresh subscription status", type="primary", use_container_width=True):
        plan = _refresh_subscription(user_email)
        st.rerun()

    # Подсказка для пользователей
    st.caption(
        "💡 After completing payment in Gumroad, return here and click "
        "**Refresh subscription status** to update your plan."
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
