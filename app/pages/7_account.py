"""
7_account.py — Страница аккаунта пользователя SubAudit
Реализовано строго по Master Specification Sheet v2.9.
Используемые разделы: Section 4, 11, 12, 13, 14, 16 (Step 6).
"""

import time
import streamlit as st
from datetime import date

# Импортируем вспомогательные модули согласно Section 4
from app.auth.supabase_auth import send_magic_link, get_user_plan, keep_alive_if_needed
from app.payments.lemon_squeezy import get_subscription_status
from app.observability.logger import log_info, log_warning

# ─────────────────────────────────────────────
# Константа кулдауна для повторной отправки magic link
# Section 11 / Section 12: COOLDOWN = 60 seconds
# ─────────────────────────────────────────────
COOLDOWN = 60  # секунды — НЕ связано с логикой keepalive (Section 11)


def _require_login() -> bool:
    """
    Проверяем, авторизован ли пользователь.
    Если нет — показываем заглушку и возвращаем False.
    Section 14: user_email хранится в session_state.
    """
    if not st.session_state.get("user_email"):
        st.warning("Вы не авторизованы. Пожалуйста, войдите через магическую ссылку.")
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
    """
    plan_labels = {
        "free": "🆓 FREE",
        "starter": "⭐ STARTER — $19/mo",
        "pro": "🚀 PRO — $49/mo",
    }
    label = plan_labels.get(plan, "❓ Неизвестный план")
    st.markdown(f"### Текущий план: **{label}**")


def _render_subscription_warning() -> None:
    """
    Показываем предупреждение, если проверка подписки завершилась с ошибкой.
    Section 13: subscription_warning, subscription_warning_reason.
    """
    if st.session_state.get("subscription_warning"):
        reason = st.session_state.get("subscription_warning_reason", "")
        if reason == "no_cache":
            st.warning(
                "⚠️ Не удалось проверить статус подписки. "
                "Используется план по умолчанию (FREE). "
                "Если вы недавно оплатили — подождите до 60 секунд и обновите страницу."
            )
        elif reason == "api_error":
            st.warning(
                "⚠️ Ошибка API при проверке подписки. "
                "Используется кешированный план. "
                "Если проблема сохраняется — обратитесь в поддержку."
            )


def _refresh_subscription(user_email: str) -> str:
    """
    Перепроверяем план через Lemon Squeezy.
    Section 13: всегда показываем st.spinner, таймаут 5s, Checkpoint 1/3.
    Section 2: план ДОЛЖЕН быть перепроверен перед PDF/Excel экспортом.
    Здесь — обновление по запросу пользователя (Checkpoint на странице аккаунта).
    """
    with st.spinner("Проверка подписки..."):
        plan = get_subscription_status(user_email)
    # Обновляем план в session_state
    st.session_state["user_plan"] = plan
    log_info(f"[7_account] Подписка обновлена для {user_email}: {plan}")
    return plan


def _render_magic_link_resend(user_email: str) -> None:
    """
    Блок повторной отправки magic link с кулдауном 60 секунд.
    Section 11 / Section 12: COOLDOWN = 60 секунд.
    Section 14: magic_link_last_sent — float Unix timestamp.
    Кулдаун НЕ связан с логикой keep_alive_if_needed (Section 11).
    """
    st.subheader("Повторная отправка ссылки для входа")

    seconds_since = _get_seconds_since_last_sent()
    remaining = None

    if seconds_since is not None and seconds_since < COOLDOWN:
        # Кулдаун ещё не истёк
        remaining = int(COOLDOWN - seconds_since)
        st.info(
            f"⏳ Повторная отправка доступна через {remaining} сек. "
            f"(кулдаун: {COOLDOWN} сек.)"
        )
        # Кнопка заблокирована во время кулдауна
        st.button(
            "Отправить магическую ссылку",
            disabled=True,
            help=f"Подождите {remaining} секунд перед повторной отправкой.",
        )
    else:
        # Кулдаун истёк или ссылка ещё не отправлялась
        if st.button("Отправить магическую ссылку"):
            success = send_magic_link(user_email)
            if success:
                # Записываем Unix timestamp момента отправки (Section 14)
                st.session_state["magic_link_last_sent"] = time.time()
                st.success(
                    f"✅ Магическая ссылка отправлена на {user_email}. "
                    "Проверьте почту."
                )
                log_info(f"[7_account] Magic link отправлен: {user_email}")
            else:
                st.error(
                    "❌ Не удалось отправить магическую ссылку. "
                    "Попробуйте позже или обратитесь в поддержку."
                )
                log_warning(f"[7_account] Не удалось отправить magic link: {user_email}")


def _render_account_info(user_email: str, plan: str) -> None:
    """
    Отображаем основную информацию об аккаунте.
    Section 14: user_email, user_plan из session_state.
    Section 2: описание возможностей по планам.
    """
    st.subheader("Информация об аккаунте")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Email:** {user_email}")
    with col2:
        _render_plan_badge(plan)

    # Краткое описание возможностей текущего плана (Section 2)
    plan_features = {
        "free": [
            "До 1 000 строк",
            "1 CSV файл на сессию",
            "Базовые метрики (Блоки 1–2)",
            "PDF экспорт с водяным знаком",
            "Без прогноза и симуляции",
        ],
        "starter": [
            "До 10 000 строк",
            "1 CSV файл на сессию",
            "Все 5 блоков метрик",
            "PDF без водяного знака",
            "Excel экспорт с формулами",
            "Прогноз (реалистичный ≥3 мес., все сценарии ≥6 мес.)",
        ],
        "pro": [
            "До 50 000 строк",
            "1 CSV файл на сессию",
            "Все 5 блоков метрик",
            "Брендированный PDF (с названием компании)",
            "Excel экспорт с формулами",
            "Прогноз (все сценарии ≥6 мес.)",
            "Симуляция + PDF экспорт",
        ],
    }

    features = plan_features.get(plan, [])
    if features:
        st.markdown("**Возможности вашего плана:**")
        for feature in features:
            st.markdown(f"- {feature}")


def _render_upgrade_cta(plan: str) -> None:
    """
    CTA для апгрейда плана — показываем, если план не PRO.
    Section 4: 6_pricing.py — страница сравнения планов.
    """
    if plan != "pro":
        st.divider()
        st.markdown("### 🚀 Хотите больше возможностей?")
        st.markdown(
            "Перейдите на **STARTER** или **PRO**, чтобы получить доступ "
            "к расширенным метрикам, прогнозам и симуляции."
        )
        if st.button("Сравнить планы и обновить"):
            # Переходим на страницу pricing (Section 4: 6_pricing.py)
            st.switch_page("pages/6_pricing.py")


def _render_logout() -> None:
    """
    Кнопка выхода из аккаунта.
    Очищаем пользовательские ключи session_state (Section 14).
    """
    st.divider()
    if st.button("🚪 Выйти из аккаунта"):
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
        ]
        for key in keys_to_clear:
            st.session_state.pop(key, None)

        st.success("Вы вышли из аккаунта.")
        log_info("[7_account] Пользователь вышел из аккаунта.")
        # Перенаправляем на landing (Section 4: 1_landing.py)
        st.switch_page("pages/1_landing.py")


# ─────────────────────────────────────────────
# Основная точка входа страницы
# ─────────────────────────────────────────────

def main() -> None:
    """
    Точка входа для страницы 7_account.py.
    Section 16 Step 6 — страница аккаунта с кулдауном magic link.
    """
    st.set_page_config(
        page_title="SubAudit — Аккаунт",
        page_icon="👤",
        layout="centered",
    )

    st.title("👤 Аккаунт")

    # ── Проверяем авторизацию (Section 14: user_email)
    _require_login()

    user_email: str = st.session_state["user_email"]

    # ── Отображаем предупреждение подписки, если есть (Section 13)
    _render_subscription_warning()

    # ── Получаем актуальный план из session_state (Section 14)
    # При необходимости перепроверяем через Lemon Squeezy (Section 13, Checkpoint)
    plan: str = st.session_state.get("user_plan", "free")

    # ── Информация об аккаунте и план (Section 2, Section 14)
    _render_account_info(user_email, plan)

    st.divider()

    # ── Кнопка ручного обновления статуса подписки (Section 13)
    if st.button("🔄 Обновить статус подписки"):
        plan = _refresh_subscription(user_email)
        st.rerun()

    # ── Постапгрейдное сообщение (Section 13: post-upgrade delay)
    if st.session_state.get("subscription_warning") and plan == "free":
        st.info(
            "💡 Если вы только что оплатили — платёжные системы могут обрабатывать "
            "до 60 секунд. Пожалуйста, обновите страницу через момент."
        )

    st.divider()

    # ── Блок повторной отправки magic link с кулдауном (Section 11, Section 12)
    # COOLDOWN = 60 секунд — строго по спецификации
    _render_magic_link_resend(user_email)

    # ── CTA апгрейда, если план не PRO (Section 4: 6_pricing.py)
    _render_upgrade_cta(plan)

    # ── Кнопка выхода (Section 14)
    _render_logout()


if __name__ == "__main__":
    main()
