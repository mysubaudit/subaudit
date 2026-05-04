"""
app/observability/logger.py
SubAudit — Master Specification Sheet v2.9
Development Order: Step 7 (Section 16)

Отвечает за:
- Инициализацию Sentry SDK (sentry-sdk==2.5.1, Section 15)
- Три публичных функции логирования: log_error(), log_warning(), log_info() (Section 4)
- Обязательную очистку PII перед любой отправкой в Sentry (Section 19)
- Distinct Sentry tags для subscription_warning_reason (Section 13)
- DSN берётся исключительно из Streamlit Secrets (Section 19)
"""

from __future__ import annotations

import re
import logging
from typing import Any

import sentry_sdk
from sentry_sdk import capture_exception, capture_message, push_scope
from sentry_sdk.integrations.logging import LoggingIntegration
import streamlit as st


# ---------------------------------------------------------------------------
# Константы PII-фильтрации (Section 19 — "All log_info() calls reviewed —
# no PII, no sensitive data")
# ---------------------------------------------------------------------------

# Регулярные выражения для обнаружения и замены персональных данных
_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Email-адреса (самый критичный PII в контексте SubAudit)
    (re.compile(r"[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9.\-]+"), "[EMAIL REDACTED]"),
    # Bearer-токены и API-ключи (например, Lemon Squeezy, Supabase JWT)
    (re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]+"), "Bearer [TOKEN REDACTED]"),
    # Supabase access_token / refresh_token в JSON-подобных строках
    (re.compile(r'"(?:access_token|refresh_token|token)"\s*:\s*"[^"]+"'), '"token": "[REDACTED]"'),
    # Общие API-ключи длиной ≥ 20 символов (hex, base64-подобные)
    (re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9_\-]{20,}(?![A-Za-z0-9])"), "[KEY REDACTED]"),
    # IPv4-адреса (могут идентифицировать пользователя)
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[IP REDACTED]"),
]


def _scrub_pii(text: str) -> str:
    """
    Применяет все PII-паттерны к строке и возвращает очищенную копию.
    Вызывается внутри каждой функции логирования ДО отправки в Sentry.

    Section 19: "All log_info() calls reviewed — no PII, no sensitive data."
    """
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _scrub_extra(extra: dict[str, Any] | None) -> dict[str, Any]:
    """
    Рекурсивно очищает PII из словаря extra-данных.
    Все строковые значения прогоняются через _scrub_pii().
    """
    if not extra:
        return {}

    cleaned: dict[str, Any] = {}
    for key, value in extra.items():
        if isinstance(value, str):
            cleaned[key] = _scrub_pii(value)
        elif isinstance(value, dict):
            cleaned[key] = _scrub_extra(value)
        elif isinstance(value, (list, tuple)):
            cleaned[key] = [
                _scrub_pii(v) if isinstance(v, str) else v for v in value
            ]
        else:
            # Числа, bool, None — безопасны, передаём as-is
            cleaned[key] = value
    return cleaned


# ---------------------------------------------------------------------------
# Инициализация Sentry
# ---------------------------------------------------------------------------

def init_sentry() -> None:
    """
    Инициализирует Sentry SDK.

    Вызывается ОДИН РАЗ из app/main.py (Section 4: "Sentry init" в main.py).
    DSN берётся из st.secrets['SENTRY_DSN'] (Section 19: "Sentry DSN in
    Secrets — not in code or README").

    Если секрет отсутствует — Sentry отключается тихо, приложение
    продолжает работу (graceful degradation).
    """
    try:
        dsn = st.secrets.get("SENTRY_DSN", "")
    except Exception:
        # st.secrets недоступен вне Streamlit-контекста (например, в тестах)
        dsn = ""

    if not dsn:
        # DSN не задан — Sentry не инициализируется, логируем локально
        logging.getLogger("subaudit").warning(
            "SENTRY_DSN не найден в Streamlit Secrets. Sentry отключён."
        )
        return

    # Интеграция стандартного logging-модуля с Sentry:
    # WARNING и выше попадают как breadcrumbs, ERROR и выше — как события
    logging_integration = LoggingIntegration(
        level=logging.WARNING,        # breadcrumbs
        event_level=logging.ERROR,    # полноценные события Sentry
    )

    sentry_sdk.init(
        dsn=dsn,
        integrations=[logging_integration],
        # Трассировка производительности отключена — не нужна для v1
        traces_sample_rate=0.0,
        # Выключаем автоматическую отправку PII (IP, user-agent и т.д.)
        send_default_pii=False,
        # Версия релиза для группировки событий в Sentry
        release="subaudit@2.9",
        environment=st.secrets.get("APP_ENV", "production"),
    )


# ---------------------------------------------------------------------------
# Публичные функции логирования (Section 4)
# ---------------------------------------------------------------------------

def log_error(
    message: str,
    exc: Exception | None = None,
    tags: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """
    Логирует ошибку уровня ERROR.

    Параметры
    ----------
    message : str
        Человекочитаемое описание ошибки. PII будет удалён автоматически.
    exc : Exception | None
        Исходное исключение для capture_exception(). Если None — отправляет
        текстовое сообщение уровня ERROR через capture_message().
    tags : dict[str, str] | None
        Sentry-теги для фильтрации/группировки.
        Section 13: обязательные теги reason='no_cache' | 'api_error'
        передаются именно здесь.
    extra : dict[str, Any] | None
        Дополнительный контекст (не индексируется Sentry, удобен при отладке).
        Все строки будут очищены от PII.

    Используется в
    --------------
    - payments/lemon_squeezy.py: HTTP 401, ошибки без кэша (Section 13)
    - auth/supabase_auth.py: критические сбои аутентификации
    """
    clean_message = _scrub_pii(message)
    clean_extra = _scrub_extra(extra)

    # Локальный вывод для отладки в dev-среде
    logging.getLogger("subaudit").error(clean_message)

    with push_scope() as scope:
        # Устанавливаем теги — Section 13 требует distinct Sentry tags
        if tags:
            for tag_key, tag_value in tags.items():
                scope.set_tag(tag_key, _scrub_pii(str(tag_value)))

        # Устанавливаем дополнительный контекст
        for key, value in clean_extra.items():
            scope.set_extra(key, value)

        if exc is not None:
            # Захватываем полный traceback
            capture_exception(exc)
        else:
            # Нет исключения — отправляем как текстовое событие ERROR
            capture_message(clean_message, level="error")


def log_warning(
    message: str,
    tags: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """
    Логирует предупреждение уровня WARNING.

    Отправляется в Sentry как breadcrumb (не как полноценное событие),
    если только уровень LoggingIntegration не поднят выше.

    Используется в
    --------------
    - auth/supabase_auth.py → keep_alive_if_needed(): "On failure → log_warning().
      Do NOT raise. Do NOT show UI error." (Section 12)
    - payments/lemon_squeezy.py: HTTP 429, кэш-фолбэк (Section 13)

    Параметры
    ----------
    message : str
        Описание ситуации. PII удаляется автоматически.
    tags : dict[str, str] | None
        Sentry-теги. Section 13: reason='api_error' передаётся здесь.
    extra : dict[str, Any] | None
        Дополнительный контекст, очищается от PII.
    """
    clean_message = _scrub_pii(message)
    clean_extra = _scrub_extra(extra)

    logging.getLogger("subaudit").warning(clean_message)

    with push_scope() as scope:
        if tags:
            for tag_key, tag_value in tags.items():
                scope.set_tag(tag_key, _scrub_pii(str(tag_value)))

        for key, value in clean_extra.items():
            scope.set_extra(key, value)

        # WARNING отправляем как message (breadcrumb в большинстве конфигураций)
        capture_message(clean_message, level="warning")


def log_info(
    message: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """
    Логирует информационное сообщение уровня INFO.

    В Sentry НЕ отправляется (ниже порога event_level=ERROR).
    Пишется только в стандартный logging-поток (stdout/stderr в Streamlit Cloud).

    ВАЖНО (Section 19): "All log_info() calls reviewed — no PII,
    no sensitive data." — PII-скраббинг применяется несмотря на то,
    что сообщение не покидает сервер, чтобы исключить утечку в stdout-логи.

    Параметры
    ----------
    message : str
        Информационное сообщение.
    extra : dict[str, Any] | None
        Дополнительный контекст. Строки очищаются от PII.
    """
    clean_message = _scrub_pii(message)
    clean_extra = _scrub_extra(extra)

    logger = logging.getLogger("subaudit")
    if clean_extra:
        logger.info("%s | extra=%s", clean_message, clean_extra)
    else:
        logger.info(clean_message)
