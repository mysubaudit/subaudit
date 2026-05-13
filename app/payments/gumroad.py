"""
app/payments/gumroad.py
=======================
Интеграция с Gumroad для проверки статуса подписки.

Заменяет lemon_squeezy.py (Section 13 спецификации).
Причина замены: Lemon Squeezy отказал в регистрации (см. CONTEXT_FOR_NEW_CHAT.md).

Строго соответствует Master Specification Sheet v2.9:
  - Section 13 : все правила работы с платёжным провайдером
  - Section 4  : место файла (app/payments/gumroad.py)
  - Section 14 : ключи session_state (subscription_warning, subscription_warning_reason)
  - Section 19 : секреты только в Streamlit Cloud, не в коде

Публичный интерфейс (тот же что у lemon_squeezy.py):
  get_subscription_status(user_email: str) → 'free' | 'starter' | 'pro'

Секреты (Streamlit Cloud Secrets / .env):
  GUMROAD_ACCESS_TOKEN      — токен доступа к Gumroad API
  GUMROAD_STARTER_PRODUCT_ID — ID продукта Starter (например "starter")
  GUMROAD_PRO_PRODUCT_ID    — ID продукта Pro (например "pro")
"""

from __future__ import annotations

import time
import streamlit as st

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None  # type: ignore[assignment]

try:
    from app.observability.logger import log_error, log_warning, log_info
except ImportError:
    # Fallback-заглушки на случай нестандартного sys.path в тестах
    def log_error(msg: str, **kwargs) -> None:  # type: ignore[misc]
        pass

    def log_warning(msg: str, **kwargs) -> None:  # type: ignore[misc]
        pass

    def log_info(msg: str, **kwargs) -> None:  # type: ignore[misc]
        pass


# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

# Section 13: timeout = 5 секунд
_REQUEST_TIMEOUT: int = 5

# Gumroad API: базовый URL для проверки продажи по email
_GUMROAD_SALES_URL: str = "https://api.gumroad.com/v2/sales"

# Section 14: ключи session_state для предупреждений о подписке
_SS_WARNING: str = "subscription_warning"
_SS_WARNING_REASON: str = "subscription_warning_reason"
_SS_CACHED_PLAN: str = "_gumroad_cached_plan"
_SS_USER_PLAN: str = "user_plan"


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _get_secrets() -> tuple[str, str, str]:
    """
    Читает секреты из Streamlit Secrets (Section 19).

    Возвращает (access_token, starter_product_id, pro_product_id).
    При отсутствии ключей возвращает пустые строки.
    """
    try:
        token = st.secrets.get("GUMROAD_ACCESS_TOKEN", "")
        starter = st.secrets.get("GUMROAD_STARTER_PRODUCT_ID", "starter")
        pro = st.secrets.get("GUMROAD_PRO_PRODUCT_ID", "pro")
    except Exception:
        # В тестовом окружении st.secrets может быть недоступен
        token = ""
        starter = "starter"
        pro = "pro"
    return token, starter, pro


def _set_warning(reason: str) -> None:
    """
    Устанавливает флаги предупреждения подписки в session_state.

    Section 13: subscription_warning=True, reason='no_cache' или 'api_error'.
    Section 14: ключи subscription_warning и subscription_warning_reason.
    """
    st.session_state[_SS_WARNING] = True
    st.session_state[_SS_WARNING_REASON] = reason


def _clear_warning() -> None:
    """
    Сбрасывает флаги предупреждения при успешной проверке.

    Section 13: "Success: subscription_warning=False. Pop subscription_warning_reason."
    """
    st.session_state[_SS_WARNING] = False
    # Pop — удаляем ключ reason при успехе (Section 13)
    st.session_state.pop(_SS_WARNING_REASON, None)


def _log_sentry(reason: str) -> None:
    """
    Логирует событие в Sentry с тегом reason (Section 13).

    Section 13: "distinct Sentry tags", reason='no_cache' или 'api_error'.
    """
    if sentry_sdk is not None:
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("reason", reason)
            sentry_sdk.capture_message(
                f"Gumroad subscription check failed: reason={reason}",
                level="warning",
            )


def _determine_plan_from_sales(
    email: str,
    token: str,
    starter_id: str,
    pro_id: str,
) -> str | None:
    """
    Выполняет HTTP-запрос к Gumroad API и определяет план пользователя.

    Возвращает 'pro', 'starter', 'free' при успехе.
    Возвращает None при сетевой ошибке или неожиданном ответе.

    Section 13:
      - timeout=5
      - HTTP 401 → log Sentry, return 'free', warning=True
      - HTTP 429 → retry один раз (не вызывается отсюда — обрабатывается выше)
    """
    if requests is None:
        return None

    # Gumroad API: проверяем продажи по email покупателя
    params = {
        "access_token": token,
        "email": email,
    }

    # Section 13: timeout = 5 секунд (константа _REQUEST_TIMEOUT)
    response = requests.get(_GUMROAD_SALES_URL, params=params, timeout=_REQUEST_TIMEOUT)

    if response.status_code == 401:
        # Section 13: HTTP 401 → Log Sentry, return 'free', warning=True
        _log_sentry("no_cache")
        log_error("Gumroad API: HTTP 401 Unauthorized", extra={"email": email})
        return "401"  # Специальный маркер для обработки в вызывающем коде

    if response.status_code == 429:
        # Сигнализируем вызывающему коду о необходимости retry
        return "429"

    if response.status_code != 200:
        log_warning(f"Gumroad API: unexpected status {response.status_code}")
        return None

    try:
        data = response.json()
    except Exception:
        log_warning("Gumroad API: failed to parse JSON response")
        return None

    if not data.get("success", False):
        log_warning("Gumroad API: success=false in response")
        return None

    # Проверяем продажи: ищем активную подписку Pro или Starter
    sales = data.get("sales", [])
    has_pro = False
    has_starter = False

    # Логируем количество продаж для отладки
    log_info(
        f"Gumroad API: found {len(sales)} sale(s) for {email}",
        extra={"email": email, "sales_count": len(sales)}
    )

    for sale in sales:
        product_id = sale.get("product_id", "")
        product_name = sale.get("product_name", "")
        # Проверяем что продажа не возвращена/отменена
        refunded = sale.get("refunded", False)
        chargedback = sale.get("chargedback", False)

        # Детальное логирование каждой продажи
        log_info(
            f"Gumroad sale: product_id={product_id}, product_name={product_name}, "
            f"refunded={refunded}, chargedback={chargedback}",
            extra={
                "product_id": product_id,
                "product_name": product_name,
                "refunded": refunded,
                "chargedback": chargedback,
                "expected_starter_id": starter_id,
                "expected_pro_id": pro_id,
            }
        )

        if refunded or chargedback:
            continue
        if product_id == pro_id:
            has_pro = True
        elif product_id == starter_id:
            has_starter = True

    if has_pro:
        log_info(f"Gumroad: user {email} has PRO plan")
        return "pro"
    if has_starter:
        log_info(f"Gumroad: user {email} has STARTER plan")
        return "starter"

    log_info(f"Gumroad: user {email} has FREE plan (no matching sales)")
    return "free"


# ---------------------------------------------------------------------------
# Публичная функция (Section 13, Section 4)
# ---------------------------------------------------------------------------

def get_subscription_status(user_email: str) -> str:
    """
    Проверяет статус подписки пользователя через Gumroad API.

    Возвращает: 'free' | 'starter' | 'pro'

    Section 13 — поведение при ошибках:
      HTTP 401  → Log Sentry, return 'free', subscription_warning=True, reason='no_cache'
      HTTP 429  → wait 1s, retry once; если опять 429 → cached or 'free', warning=True
      Error + no cache → return 'free', warning=True, reason='no_cache', Sentry no_cache
      Error + cache    → return cached, warning=True, reason='api_error', Sentry api_error
      Success          → warning=False, pop reason, update user_plan, update cache

    Section 13: Always st.spinner("Verifying subscription...") — never silent
    Section 13: requests.get(..., timeout=5)
    Section 13: Post-upgrade message при subscription_warning сразу после апгрейда
    """
    token, starter_id, pro_id = _get_secrets()

    # Получаем кешированный план из session_state (Section 13)
    cached_plan: str | None = st.session_state.get(_SS_CACHED_PLAN, None)

    # Section 13: всегда показываем спиннер
    with st.spinner("Verifying subscription..."):
        try:
            plan_or_code = _determine_plan_from_sales(
                user_email, token, starter_id, pro_id
            )

            # --- Обработка HTTP 429: wait 1s, retry once (Section 13) ---
            if plan_or_code == "429":
                time.sleep(1)  # Section 13: "Wait 1s, retry once"
                try:
                    plan_or_code = _determine_plan_from_sales(
                        user_email, token, starter_id, pro_id
                    )
                except Exception:
                    plan_or_code = None

                if plan_or_code == "429" or plan_or_code is None:
                    # Section 13: "Still failing → cached or 'free'. Set subscription_warning=True."
                    _set_warning("no_cache" if cached_plan is None else "api_error")
                    _log_sentry("no_cache" if cached_plan is None else "api_error")
                    return cached_plan if cached_plan is not None else "free"

            # --- Обработка HTTP 401 (Section 13) ---
            if plan_or_code == "401":
                _set_warning("no_cache")
                _log_sentry("no_cache")
                return "free"

            # --- None означает сетевую/parse ошибку ---
            if plan_or_code is None:
                if cached_plan is not None:
                    # Section 13: "Error — cache present → Return cached plan, warning=True, reason='api_error'"
                    _set_warning("api_error")
                    _log_sentry("api_error")
                    return cached_plan
                else:
                    # Section 13: "Error — no cache → Return 'free', warning=True, reason='no_cache'"
                    _set_warning("no_cache")
                    _log_sentry("no_cache")
                    return "free"

            # --- Успешный ответ (Section 13) ---
            plan: str = plan_or_code  # 'free' | 'starter' | 'pro'

            # Section 13: "Success: subscription_warning=False. Pop subscription_warning_reason."
            _clear_warning()

            # Section 13: "Update user_plan"
            st.session_state[_SS_USER_PLAN] = plan

            # Обновляем кеш для будущих запросов при ошибках
            st.session_state[_SS_CACHED_PLAN] = plan

            return plan

        except Exception as exc:
            # Непредвиденная ошибка (сеть, timeout и т.д.)
            log_error(f"Gumroad get_subscription_status exception: {exc}")

            if cached_plan is not None:
                # Section 13: cache present → return cached, reason='api_error'
                _set_warning("api_error")
                _log_sentry("api_error")
                return cached_plan
            else:
                # Section 13: no cache → return 'free', reason='no_cache'
                _set_warning("no_cache")
                _log_sentry("no_cache")
                return "free"
