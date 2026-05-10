"""
app/payments/gumroad.py
Замена lemon_squeezy.py — платёжная система Gumroad.
Все требования по Section 13 спецификации v2.9 сохранены без изменений.
"""

import time
import streamlit as st
import requests
import sentry_sdk

from app.observability.logger import log_error, log_warning, log_info

# ---------------------------------------------------------------------------
# Константы — секреты хранятся в Streamlit Secrets (Section 19)
# ---------------------------------------------------------------------------
_ACCESS_TOKEN = st.secrets["GUMROAD_ACCESS_TOKEN"]
_STARTER_PRODUCT_ID = st.secrets["GUMROAD_STARTER_PRODUCT_ID"]  # "starter"
_PRO_PRODUCT_ID = st.secrets["GUMROAD_PRO_PRODUCT_ID"]          # "pro"

# Базовый URL Gumroad API
_GUMROAD_API = "https://api.gumroad.com/v2"

# Таймаут запроса — Section 13
_TIMEOUT = 5  # секунд


def get_subscription_status(user_email: str) -> str:
    """
    Возвращает план пользователя: 'free' / 'starter' / 'pro'.

    Логика по Section 13:
    - Всегда показывать st.spinner("Verifying subscription...")
    - HTTP 429 → ждать 1с, повторить 1 раз
    - HTTP 401 → Sentry, вернуть 'free', subscription_warning=True
    - Ошибка без кэша → 'free', reason='no_cache'
    - Ошибка с кэшем → кэш, reason='api_error'
    - Успех → очистить subscription_warning
    - Re-verify перед PDF/Excel (Section 2)
    """
    with st.spinner("Verifying subscription..."):
        plan = _fetch_plan(user_email)
    return plan


def _fetch_plan(user_email: str) -> str:
    """Внутренняя логика получения плана с retry и обработкой ошибок."""

    # Сначала проверяем PRO, затем STARTER
    for product_id, plan_name in [
        (_PRO_PRODUCT_ID, "pro"),
        (_STARTER_PRODUCT_ID, "starter"),
    ]:
        result = _check_license(user_email, product_id, plan_name)
        if result == "found":
            # Успех — очищаем предупреждения (Section 13: Success)
            st.session_state["subscription_warning"] = False
            st.session_state.pop("subscription_warning_reason", None)
            st.session_state["user_plan"] = plan_name
            log_info(f"Plan verified: {plan_name}")
            return plan_name
        if result == "error":
            # Ошибка уже обработана внутри _check_license
            return _fallback_plan()

    # Ни один продукт не найден — пользователь на бесплатном плане
    st.session_state["subscription_warning"] = False
    st.session_state.pop("subscription_warning_reason", None)
    st.session_state["user_plan"] = "free"
    return "free"


def _check_license(user_email: str, product_id: str, plan_name: str) -> str:
    """
    Проверяет наличие активной лицензии Gumroad для email + product_id.
    Возвращает: 'found' | 'not_found' | 'error'

    Gumroad API: GET /v2/sales — фильтрация по email и product_permalink.
    """
    url = f"{_GUMROAD_API}/sales"
    headers = {"Authorization": f"Bearer {_ACCESS_TOKEN}"}
    params = {
        "email": user_email,
        "product_permalink": product_id,
    }

    try:
        response = _get_with_retry(url, headers=headers, params=params)
    except _RetryExhausted:
        # HTTP 429 — retry исчерпан (Section 13)
        log_warning(f"Gumroad 429 retry exhausted for {plan_name}")
        st.session_state["subscription_warning"] = True
        return "error"
    except _AuthError:
        # HTTP 401 — логируем в Sentry с тегами (Section 13)
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("reason", "no_cache")
            scope.set_tag("plan_checked", plan_name)
            sentry_sdk.capture_message("Gumroad API 401 Unauthorized", level="error")
        log_error(f"Gumroad 401 for {plan_name}")
        st.session_state["subscription_warning"] = True
        st.session_state["subscription_warning_reason"] = "no_cache"
        return "error"
    except Exception as exc:
        # Прочие ошибки
        log_error(f"Gumroad API error for {plan_name}: {exc}")
        st.session_state["subscription_warning"] = True
        return "error"

    # Разбираем ответ
    if response.status_code == 200:
        data = response.json()
        sales = data.get("sales", [])
        # Ищем активную продажу (подписку) для этого email
        for sale in sales:
            if _is_active_sale(sale, user_email):
                return "found"
        return "not_found"

    # Неожиданный статус
    log_warning(f"Gumroad unexpected status {response.status_code} for {plan_name}")
    return "not_found"


def _is_active_sale(sale: dict, user_email: str) -> bool:
    """
    Проверяет, является ли продажа активной подпиской для данного email.
    Gumroad возвращает email покупателя в поле 'email'.
    Подписка считается активной если: не отменена и не истекла.
    """
    # Проверяем email покупателя
    if sale.get("email", "").lower() != user_email.lower():
        return False

    # Подписка отменена — не считается активной
    if sale.get("subscription_cancelled_at") is not None:
        return False

    # Подписка истекла — не считается активной
    if sale.get("subscription_ended_at") is not None:
        return False

    return True


def _get_with_retry(url: str, headers: dict, params: dict) -> requests.Response:
    """
    GET-запрос с единственным retry при HTTP 429 (Section 13).
    Raises: _RetryExhausted, _AuthError, requests.RequestException
    """
    response = requests.get(url, headers=headers, params=params, timeout=_TIMEOUT)

    if response.status_code == 429:
        # Ждём 1 секунду и повторяем один раз (Section 13)
        time.sleep(1)
        response = requests.get(url, headers=headers, params=params, timeout=_TIMEOUT)
        if response.status_code == 429:
            raise _RetryExhausted()

    if response.status_code == 401:
        raise _AuthError()

    return response


def _fallback_plan() -> str:
    """
    Возвращает кэшированный план или 'free' при ошибке API (Section 13).
    Устанавливает subscription_warning с reason.
    """
    cached = st.session_state.get("user_plan")

    if cached and cached in ("starter", "pro"):
        # Есть кэш — возвращаем его с предупреждением
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("reason", "api_error")
            sentry_sdk.capture_message("Gumroad API error — using cached plan", level="warning")
        st.session_state["subscription_warning"] = True
        st.session_state["subscription_warning_reason"] = "api_error"
        log_warning(f"Gumroad API error — fallback to cached plan: {cached}")
        return cached
    else:
        # Нет кэша — возвращаем 'free'
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("reason", "no_cache")
            sentry_sdk.capture_message("Gumroad API error — no cache, returning free", level="warning")
        st.session_state["subscription_warning"] = True
        st.session_state["subscription_warning_reason"] = "no_cache"
        log_warning("Gumroad API error — no cache, returning free")
        return "free"


# ---------------------------------------------------------------------------
# Внутренние исключения
# ---------------------------------------------------------------------------

class _RetryExhausted(Exception):
    """HTTP 429 — retry исчерпан."""


class _AuthError(Exception):
    """HTTP 401 — неверный токен."""
