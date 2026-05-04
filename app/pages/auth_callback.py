"""
auth_callback.py — Верификация magic link токена и инициализация сессии.

Согласно Section 4 (File Structure): app/pages/auth_callback.py
Согласно Section 16 (Development Order), Step 6:
    auth/supabase_auth.py + payments/lemon_squeezy.py + auth_callback.py
    + 6_pricing.py + 7_account.py

Порядок действий при успешной верификации (Section 12):
    1. verify_magic_link(token) → user_dict
    2. keep_alive_if_needed(user_email)  ← вызывать ПОСЛЕ verify, НЕ внутри него
    3. get_subscription_status(user_email) — Checkpoint 1 (Section 13)
    4. Инициализация session_state (Section 14)
    5. Редирект на Dashboard или Upload
"""

import time
import streamlit as st

# Импорт функций аутентификации (Section 12)
from app.auth.supabase_auth import (
    verify_magic_link,
    keep_alive_if_needed,
)

# Импорт функции проверки подписки — Checkpoint 1 (Section 13)
from app.payments.lemon_squeezy import get_subscription_status

# Импорт логгера (Section 7, Section 4: observability/logger.py)
from app.observability.logger import log_error, log_warning, log_info


# ---------------------------------------------------------------------------
# Вспомогательная функция: инициализация ключей сессии (Section 14)
# ---------------------------------------------------------------------------

def _init_session_defaults() -> None:
    """
    Устанавливает значения по умолчанию для ключей session_state,
    которые ещё не были инициализированы.
    Согласно Section 14 (Session State & Memory).
    """
    defaults: dict = {
        # Данные пользователя
        "user_email": None,
        "user_plan": "free",

        # Данные о подписке (Section 13)
        "subscription_warning": False,
        "subscription_warning_reason": None,

        # Временны́е метки сессии (Section 14)
        "session_start": time.time(),       # Unix timestamp — 8-hour MAX AGE
        "last_activity": time.time(),       # обновляется только при явных действиях пользователя

        # Флаг keepalive (Section 12: keep_alive_if_needed)
        # Тип: date — устанавливается внутри keep_alive_if_needed()
        # "last_keepalive_date" — НЕ инициализируем здесь намеренно:
        #   отсутствие ключа == "ещё не выполнялось сегодня" (Section 12)

        # Данные файла и метрик — пустые до загрузки
        "df_clean": None,
        "column_mapping": None,
        "cleaning_report": None,
        "metrics_dict": None,
        "data_quality_flags": None,
        "forecast_dict": None,
        "simulation_dict": None,

        # Данные компании для PDF (Section 14)
        "company_name": {"display_name": "", "filename_safe_name": ""},
        "currency": "USD",

        # Дебаунс-флаги экспорта (Section 14)
        "pdf_generating": False,
        "excel_generating": False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ---------------------------------------------------------------------------
# Основная логика страницы
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Точка входа для auth_callback.py.
    Читает токен из query-параметров, верифицирует magic link,
    инициализирует сессию и перенаправляет пользователя.
    """

    st.set_page_config(
        page_title="SubAudit — Verifying login...",
        page_icon="🔐",
        layout="centered",
    )

    # -------------------------------------------------------------------
    # Шаг 1: Получение токена из URL (query params)
    # Supabase передаёт токен через параметр "token" или "access_token"
    # -------------------------------------------------------------------
    query_params = st.query_params

    # Supabase magic link может передавать токен в разных параметрах
    token: str | None = (
        query_params.get("token")
        or query_params.get("access_token")
    )

    if not token:
        # Токен отсутствует — пользователь попал сюда случайно или ссылка устарела
        st.error(
            "❌ Invalid or expired login link. "
            "Please request a new magic link from the login page."
        )
        log_warning("auth_callback: токен отсутствует в query_params")
        st.stop()
        return

    # -------------------------------------------------------------------
    # Шаг 2: Верификация magic link токена (Section 12)
    # verify_magic_link(token: str) → user_dict or None
    # -------------------------------------------------------------------
    with st.spinner("Verifying your login link..."):
        user_dict: dict | None = verify_magic_link(token)

    if user_dict is None:
        # Верификация не прошла — токен недействителен или истёк
        st.error(
            "❌ Login link is invalid or has expired. "
            "Please request a new magic link."
        )
        log_warning("auth_callback: verify_magic_link вернул None")
        st.stop()
        return

    # Извлекаем email из результата верификации
    user_email: str | None = (
        user_dict.get("email")
        or user_dict.get("user", {}).get("email")
    )

    if not user_email:
        # Структура ответа неожиданная — логируем и прерываем
        st.error(
            "❌ Could not retrieve user information. "
            "Please try logging in again."
        )
        log_error(
            "auth_callback: email не найден в user_dict",
            extra={"user_dict_keys": list(user_dict.keys())},
        )
        st.stop()
        return

    # -------------------------------------------------------------------
    # Шаг 3: Инициализация значений session_state по умолчанию (Section 14)
    # Делается ДО записи пользовательских данных
    # -------------------------------------------------------------------
    _init_session_defaults()

    # Записываем email в сессию
    st.session_state["user_email"] = user_email

    # Обновляем last_activity — вход является явным действием пользователя
    st.session_state["last_activity"] = time.time()

    log_info(f"auth_callback: пользователь успешно верифицирован — {user_email}")

    # -------------------------------------------------------------------
    # Шаг 4: keep_alive_if_needed — ПОСЛЕ verify_magic_link, НЕ внутри него
    # (Section 12: "On user login (auth_callback.py), AFTER verify_magic_link() succeeds.
    #  Do NOT call inside verify_magic_link().")
    # -------------------------------------------------------------------
    keep_alive_if_needed(user_email)

    # -------------------------------------------------------------------
    # Шаг 5: Проверка подписки — Checkpoint 1 (Section 13)
    # "Always st.spinner('Verifying subscription...') — never silent"
    # -------------------------------------------------------------------
    with st.spinner("Verifying subscription..."):
        plan: str = get_subscription_status(user_email)

    # Записываем план в сессию (Section 14: user_plan)
    st.session_state["user_plan"] = plan

    log_info(f"auth_callback: план пользователя — {plan}")

    # -------------------------------------------------------------------
    # Шаг 6: Обработка subscription_warning (Section 13)
    # get_subscription_status уже устанавливает subscription_warning
    # и subscription_warning_reason в session_state внутри lemon_squeezy.py.
    # Здесь отображаем предупреждение пользователю, если оно есть.
    # -------------------------------------------------------------------
    if st.session_state.get("subscription_warning"):
        reason = st.session_state.get("subscription_warning_reason", "")

        if reason == "no_cache":
            # Section 13: HTTP 401 или ошибка без кэша → возврат 'free'
            st.warning(
                "⚠️ Could not verify your subscription at this time. "
                "You have been granted free access temporarily. "
                "If you have an active plan, please refresh in a moment."
            )
        elif reason == "api_error":
            # Section 13: ошибка API, кэш присутствует → возвращён кэшированный план
            st.warning(
                "⚠️ Subscription service is temporarily unavailable. "
                "Your previous plan has been restored from cache."
            )
        # Section 13: "Payment processors may take up to 60 seconds"
        # Это сообщение показывается только если предупреждение сработало сразу после апгрейда.
        # Логика определения post-upgrade находится в lemon_squeezy.py;
        # здесь показываем универсальное сообщение.

    # -------------------------------------------------------------------
    # Шаг 7: Успешный вход — редирект
    # Если у пользователя уже есть загруженные данные — на Dashboard,
    # иначе — на Upload. В момент первого входа df_clean всегда None.
    # -------------------------------------------------------------------
    st.success(f"✅ Welcome! You are now logged in as **{user_email}**.")
    st.info(f"Your current plan: **{plan.upper()}**")

    # Небольшая пауза, чтобы пользователь увидел сообщение об успехе
    time.sleep(1.5)

    # Перенаправление: если данные уже загружены — на Dashboard, иначе — на Upload
    # (Section 4: 2_upload.py, 5_dashboard.py)
    if st.session_state.get("df_clean") is not None:
        st.switch_page("pages/5_dashboard.py")
    else:
        st.switch_page("pages/2_upload.py")


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

if __name__ == "__main__" or True:
    # Streamlit запускает файл напрямую — вызываем main()
    main()
