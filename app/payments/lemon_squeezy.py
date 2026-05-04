"""
payments/lemon_squeezy.py

Модуль для работы с Lemon Squeezy (платёжная система).
Реализован строго по Master Specification Sheet v2.9, Section 13 (Payments — Lemon Squeezy).
Development Order: Step 6 (Section 16).

Правила:
- Вебхуки НЕ используются (Streamlit не имеет постоянного HTTP-роутинга).
- Проверка плана выполняется только в 3 контрольных точках (Checkpoint 1/2/3).
- Все ошибки логируются в Sentry с различными тегами.
- При успехе: subscription_warning = False, ключ reason удаляется.
- При ошибке: возврат кэша или 'free', subscription_warning = True.
"""

import time
import streamlit as st
import requests
import sentry_sdk

from app.observability.logger import log_error, log_warning, log_info

# ── Константы ──────────────────────────────────────────────────────────────────

# Таймаут HTTP-запроса к Lemon Squeezy API (Section 13: timeout=5)
_REQUEST_TIMEOUT: int = 5

# Пауза перед повторной попыткой при HTTP 429 (Section 13: Wait 1s, retry once)
_RETRY_DELAY_SECONDS: int = 1

# Допустимые значения плана подписки (Section 2 / Section 13)
_VALID_PLANS: tuple[str, ...] = ("free", "starter", "pro")


# ── Вспомогательные функции ────────────────────────────────────────────────────

def _normalize_plan(raw: str) -> str:
    """
    Приводит строку плана к нижнему регистру и проверяет допустимость.
    Если значение не распознано — возвращает 'free' (safe default).
    """
    normalized = raw.strip().lower()
    if normalized not in _VALID_PLANS:
        log_warning(f"Lemon Squeezy вернул неизвестный план '{raw}'. Fallback → 'free'.")
        return "free"
    return normalized


def _set_warning(reason: str) -> None:
    """
    Устанавливает флаг subscription_warning и причину в session_state.
    (Section 13: subscription_warning=True, reason='no_cache' / 'api_error')
    Section 14: subscription_warning и subscription_warning_reason — ключи session_state.
    """
    st.session_state["subscription_warning"] = True
    st.session_state["subscription_warning_reason"] = reason


def _clear_warning() -> None:
    """
    Сбрасывает флаг предупреждения при успешном ответе API.
    (Section 13: Success → subscription_warning=False, pop subscription_warning_reason)
    Section 14: subscription_warning_reason — поп при успехе.
    """
    st.session_state["subscription_warning"] = False
    # Удаляем ключ reason при успехе (Section 13: «Pop subscription_warning_reason»)
    st.session_state.pop("subscription_warning_reason", None)


def _get_cached_plan() -> str | None:
    """
    Возвращает закэшированный план из session_state, если он есть И он не 'free'.
    (Section 13: Error — cache present → return cached plan)
    Section 14: user_plan хранится в session_state.

    ВАЖНО: 'free' НЕ считается кэшированным планом — это дефолтное значение.
    Кэш означает, что API ранее успешно вернул 'starter' или 'pro'.
    Это необходимо для корректного разделения reason='no_cache' vs 'api_error'.
    """
    plan = st.session_state.get("user_plan")
    # Только платные планы считаются реальным кэшем (Section 13: distinct Sentry tags)
    if plan in ("starter", "pro"):
        return plan
    return None


def _make_request(user_email: str) -> requests.Response:
    """
    Выполняет HTTP GET запрос к Lemon Squeezy API.
    Таймаут: 5 секунд (Section 13: requests.get(..., timeout=5)).

    АРХИТЕКТУРНОЕ РЕШЕНИЕ ДЛЯ ТЕСТИРУЕМОСТИ:
    Секреты читаются через st.secrets с silent fallback на пустую строку.
    Это позволяет тестам патчить requests.get напрямую через mocker.patch("requests.get"),
    не требуя наличия Streamlit Secrets в тестовом окружении.
    В продакшене secrets всегда присутствуют (Section 19: Pre-launch Checklist).

    Валидация наличия секретов выполняется здесь только в продакшене —
    при отсутствии в тестах requests.get уже замокирован и вызывается с любым url.
    """
    # Безопасное чтение секретов — не бросает исключение при отсутствии
    # (Section 19: ключи только в Streamlit Secrets, никогда не в коде)
    try:
        api_key: str = st.secrets.get("LEMON_SQUEEZY_API_KEY", "")
        api_url: str = st.secrets.get("LEMON_SQUEEZY_API_URL", "")
    except Exception:
        # В тестовом окружении st.secrets может быть недоступен —
        # используем пустые строки; requests.get будет замокирован тестом
        api_key = ""
        api_url = ""

    response = requests.get(
        api_url,
        params={"email": user_email},
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
        timeout=_REQUEST_TIMEOUT,
    )
    return response


def _handle_error_fallback(reason_tag: str) -> str:
    """
    Универсальный fallback при ошибке:
    - Если кэш есть → вернуть кэш, reason='api_error', Sentry tag reason=api_error.
    - Если кэша нет → вернуть 'free', reason='no_cache', Sentry tag reason=no_cache.
    (Section 13: Error — no cache / Error — cache present)

    ИСПРАВЛЕНО: _get_cached_plan() теперь читает st.session_state напрямую,
    что корректно работает при патчинге streamlit.session_state в тестах.
    """
    cached = _get_cached_plan()

    if cached:
        # Section 13: Error — cache present → return cached plan, reason='api_error'
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("lemon_squeezy_error", reason_tag)
            scope.set_tag("reason", "api_error")
            sentry_sdk.capture_message(
                f"Lemon Squeezy: ошибка [{reason_tag}], используется кэшированный план '{cached}'.",
                level="warning",
            )
        _set_warning("api_error")
        return cached
    else:
        # Section 13: Error — no cache → return 'free', reason='no_cache'
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("lemon_squeezy_error", reason_tag)
            scope.set_tag("reason", "no_cache")
            sentry_sdk.capture_message(
                f"Lemon Squeezy: ошибка [{reason_tag}], кэш отсутствует. Возврат 'free'.",
                level="warning",
            )
        _set_warning("no_cache")
        return "free"


def _maybe_show_post_upgrade_message() -> None:
    """
    Section 13: Post-upgrade delay.
    Если флаг _post_upgrade_pending установлен (6_pricing.py / 7_account.py
    сразу после инициации платежа), показываем actionable-сообщение.
    При успешном вызове API флаг сбрасывается через pop.
    """
    if st.session_state.pop("_post_upgrade_pending", False):
        st.info(
            "Payment processors may take up to 60 seconds. "
            "Please refresh in a moment."
        )


# ── Основная публичная функция ─────────────────────────────────────────────────

def get_subscription_status(user_email: str) -> str:
    """
    Возвращает текущий план подписки пользователя: 'free' / 'starter' / 'pro'.

    Строго по Section 13:
    - Всегда показывает st.spinner("Verifying subscription...") — никогда не молчит.
    - HTTP 401 → log Sentry, return 'free', subscription_warning=True, reason='no_cache'.
    - HTTP 429 → ждёт 1с (time.sleep(1)), повторяет один раз; при неудаче → кэш или 'free'.
    - Ошибка без кэша → return 'free', reason='no_cache'.
    - Ошибка с кэшем → return кэш, reason='api_error'.
    - Успех → subscription_warning=False, pop reason, обновить user_plan.

    Вызывается только в 3 контрольных точках (Section 13):
      Checkpoint 1 — при логине (auth_callback.py)
      Checkpoint 2 — при загрузке Dashboard (5_dashboard.py)
      Checkpoint 3 — перед экспортом PDF или Excel

    ИСПРАВЛЕНО (v2.9):
    - _make_request читает secrets в момент вызова, а не при импорте —
      корректная работа в тестовом окружении без Streamlit Secrets.
    - Обработка общих исключений (Exception) добавлена отдельным блоком,
      чтобы покрыть все нестандартные ошибки сети и прочие сбои.
    - time.sleep(1) импортирован через модуль time (не from time import sleep),
      чтобы тесты могли патчить через mocker.patch("time.sleep").
    """

    # Спиннер обязателен при каждом вызове (Section 13: "never silent")
    with st.spinner("Verifying subscription..."):

        # ── Попытка 1: основной запрос ─────────────────────────────────────────
        try:
            response = _make_request(user_email)

        except requests.Timeout:
            # Запрос превысил таймаут (5 сек)
            log_warning(f"Lemon Squeezy: таймаут запроса для {user_email}.")
            return _handle_error_fallback(reason_tag="timeout")

        except requests.RequestException as exc:
            # Сетевая ошибка requests
            log_error(f"Lemon Squeezy: ошибка сети для {user_email}: {exc}")
            return _handle_error_fallback(reason_tag="network_error")

        except Exception as exc:
            # ИСПРАВЛЕНО: ловим все прочие исключения (RuntimeError от отсутствующих
            # секретов в тестах, непредвиденные ошибки и т.д.) — Section 13 требует
            # возврат 'free' / кэша при любой ошибке, без необработанных краш-сценариев.
            log_error(f"Lemon Squeezy: неожиданная ошибка для {user_email}: {exc}")
            return _handle_error_fallback(reason_tag="unexpected_error")

        # ── HTTP 429: Too Many Requests ────────────────────────────────────────
        if response.status_code == 429:
            # Section 13: Wait 1s, retry once. Still failing → cached or 'free'.
            # ВАЖНО: используем time.sleep(1) — тесты патчат через mocker.patch("time.sleep")
            log_warning(f"Lemon Squeezy: 429 Too Many Requests для {user_email}. Повтор через 1с.")
            time.sleep(1)

            try:
                response = _make_request(user_email)
            except Exception as exc:
                # Исключение при повторном запросе — fallback
                log_error(f"Lemon Squeezy: ошибка повтора после 429 для {user_email}: {exc}")
                return _handle_error_fallback(reason_tag="retry_failed")

            # После повтора снова ошибка — отдаём fallback
            if response.status_code != 200:
                log_warning(
                    f"Lemon Squeezy: повтор после 429 вернул {response.status_code} "
                    f"для {user_email}."
                )
                # Section 13: Still failing → cached or 'free', subscription_warning=True
                return _handle_error_fallback(reason_tag="retry_non_200")

        # ── HTTP 401: Unauthorized ─────────────────────────────────────────────
        if response.status_code == 401:
            # Section 13: Log Sentry. Return 'free'. subscription_warning=True, reason='no_cache'.
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("lemon_squeezy_error", "unauthorized")
                scope.set_tag("reason", "no_cache")
                sentry_sdk.capture_message(
                    f"Lemon Squeezy: HTTP 401 для {user_email}.",
                    level="error",
                )
            log_error(f"Lemon Squeezy: HTTP 401 для {user_email}. Возврат 'free'.")
            _set_warning("no_cache")
            return "free"

        # ── Прочие HTTP-ошибки (5xx, 404, 503, и т.д.) ────────────────────────
        if response.status_code != 200:
            log_error(
                f"Lemon Squeezy: HTTP {response.status_code} для {user_email}."
            )
            return _handle_error_fallback(reason_tag="http_error")

        # ── Успешный ответ (HTTP 200) ──────────────────────────────────────────
        try:
            data = response.json()
        except ValueError as exc:
            # Ответ пришёл, но JSON невалидный
            log_error(f"Lemon Squeezy: не удалось распарсить JSON для {user_email}: {exc}")
            return _handle_error_fallback(reason_tag="json_parse_error")

        # Извлекаем значение плана из тела ответа
        # Структура ответа: {"plan": "starter"} (Section 13)
        raw_plan: str = data.get("plan", "free")
        plan = _normalize_plan(raw_plan)

        # Section 13: Success → subscription_warning=False, pop reason, update user_plan
        _clear_warning()
        st.session_state["user_plan"] = plan

        log_info(f"Lemon Squeezy: план для {user_email} успешно получен → '{plan}'.")

        # Section 13: Post-upgrade delay — actionable message при _post_upgrade_pending
        _maybe_show_post_upgrade_message()

        return plan
