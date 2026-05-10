"""
auth/supabase_auth.py
SubAudit — Master Specification Sheet v2.9
Раздел: Section 12 (Authentication), Section 11 (keep_alive_if_needed),
        Section 16 Step 6 (Development Order)

CHANGELOG:
- sign_in_with_otp: dict → именованный параметр email=email
- verify_otp: dict → именованные параметры token_hash=token, type="magiclink"
- _get_supabase_client: поддержка обоих форматов secrets
  ([supabase] url/anon_key  ИЛИ  SUPABASE_URL/SUPABASE_KEY)
- get_user_plan: таблица user_plans → subscriptions (реальная таблица)
- send_magic_link: добавлен redirect_to из secrets (опционально)
- Подробное логирование ошибки для диагностики
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import streamlit as st
from supabase import create_client, Client

from app.observability.logger import log_error, log_warning, log_info

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

COOLDOWN: int = 60  # секунды — используется в 7_account.py

# ---------------------------------------------------------------------------
# Инициализация клиента Supabase
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Client:
    """
    Создаёт клиент Supabase.
    Поддерживает ДВА формата secrets.toml:

    Формат А (плоский):          Формат Б (секция [supabase]):
      SUPABASE_URL = "..."         [supabase]
      SUPABASE_KEY = "..."         url      = "..."
                                   anon_key = "..."
    """
    # Пробуем формат Б — [supabase] секция
    if "supabase" in st.secrets:
        url: str = st.secrets["supabase"]["url"]
        # anon_key или key — принимаем оба варианта
        key: str = (
            st.secrets["supabase"].get("anon_key")
            or st.secrets["supabase"].get("key")
            or st.secrets["supabase"].get("service_role_key")
        )
    else:
        # Формат А — плоские ключи
        url = st.secrets["SUPABASE_URL"]
        key = (
            st.secrets.get("SUPABASE_ANON_KEY")
            or st.secrets.get("SUPABASE_KEY")
        )

    if not url or not key:
        raise ValueError(
            "Supabase credentials not found in secrets. "
            "Expected [supabase] url + anon_key  OR  SUPABASE_URL + SUPABASE_KEY"
        )

    return create_client(url, key)


# ---------------------------------------------------------------------------
# send_magic_link — Section 12
# ---------------------------------------------------------------------------

def send_magic_link(email: str) -> bool:
    """
    Отправляет magic link на указанный email через Supabase Auth.

    Параметры:
        email (str): адрес электронной почты пользователя

    Возвращает:
        bool: True — письмо успешно отправлено, False — произошла ошибка

    Spec ref: Section 12.
    Cooldown (60 сек) применяется на уровне 7_account.py — не здесь.
    """
    try:
        client: Client = _get_supabase_client()

        # Redirect URL — опционально из secrets
        # В Supabase Dashboard → Auth → URL Configuration
        # добавить: https://subaudit.streamlit.app/*
        redirect_url: str | None = st.secrets.get("SUPABASE_REDIRECT_URL") or None

        # Supabase Python SDK v2: sign_in_with_otp принимает именованные параметры
        if redirect_url:
            client.auth.sign_in_with_otp(
                email=email,
                options={"email_redirect_to": redirect_url},
            )
        else:
            client.auth.sign_in_with_otp(email=email)

        # Section 19: email — PII, не логируем через log_info
        log_info("magic_link_sent")
        return True

    except Exception as exc:
        # Подробное логирование для диагностики
        log_error(
            "send_magic_link_failed",
            exc=exc,
            extra={
                "email": email,
                "exc_type": type(exc).__name__,
                "exc_detail": str(exc),
            },
        )
        return False


# ---------------------------------------------------------------------------
# verify_magic_link — Section 12
# ---------------------------------------------------------------------------

def verify_magic_link(token: str) -> dict | None:
    """
    Верифицирует токен magic link и возвращает словарь с данными пользователя.

    Параметры:
        token (str): токен из URL magic link

    Возвращает:
        dict с ключами {'email', 'id', 'user_metadata'} или None при ошибке

    Spec ref: Section 12.
    keep_alive_if_needed() вызывается ПОСЛЕ в auth_callback.py — не здесь.

    ИСПРАВЛЕНИЕ:
        Было:  client.auth.verify_otp({"token_hash": token, "type": "magiclink"})
        Стало: client.auth.verify_otp(token_hash=token, type="magiclink")
        Причина: Supabase Python SDK v2 принимает именованные параметры,
                 словарь позиционно игнорировался → ошибка верификации.
    """
    try:
        client: Client = _get_supabase_client()

        # SDK v2: именованные параметры, не словарь
        response = client.auth.verify_otp(
            token_hash=token,
            type="magiclink",
        )

        if response and response.user:
            user_dict = {
                "email": response.user.email,
                "id": response.user.id,
                "user_metadata": response.user.user_metadata,
            }
            # Section 19: email — PII, не логируем через log_info
            log_info("verify_magic_link_success")
            return user_dict

        log_warning(
            "verify_magic_link_no_user",
            extra={"token_prefix": token[:8] if len(token) >= 8 else token},
        )
        return None

    except Exception as exc:
        log_error(
            "verify_magic_link_failed",
            exc=exc,
            extra={
                "token_prefix": token[:8] if len(token) >= 8 else token,
                "exc_type": type(exc).__name__,
                "exc_detail": str(exc),
            },
        )
        return None


# ---------------------------------------------------------------------------
# get_user_plan — Section 12
# ---------------------------------------------------------------------------

def get_user_plan(user_email: str) -> str:
    """
    Возвращает план пользователя из таблицы subscriptions в Supabase.

    Параметры:
        user_email (str): email пользователя

    Возвращает:
        str: 'free' | 'starter' | 'pro'

    Spec ref: Section 12.
    """
    try:
        client: Client = _get_supabase_client()

        # Таблица: subscriptions
        # Колонки: email, plan
        # limit(1) вместо single() — single() падает если 0 строк
        response = (
            client
            .table("subscriptions")
            .select("plan")
            .eq("email", user_email)
            .limit(1)
            .execute()
        )

        # limit(1) возвращает list
        if response.data and len(response.data) > 0:
            plan = response.data[0].get("plan", "free")
        else:
            plan = "free"

        # Валидация — Section 2: три допустимых плана
        if plan not in ("free", "starter", "pro"):
            log_warning(
                "get_user_plan_invalid_value",
                extra={"email": user_email, "plan": plan},
            )
            return "free"

        return plan

    except Exception as exc:
        log_error(
            "get_user_plan_failed",
            exc=exc,
            extra={
                "email": user_email,
                "exc_type": type(exc).__name__,
                "exc_detail": str(exc),
            },
        )
        return "free"


# ---------------------------------------------------------------------------
# keep_alive_if_needed — Section 11
# ---------------------------------------------------------------------------

def keep_alive_if_needed(user_email: str) -> None:
    """
    Вторичный keepalive для предотвращения паузы Supabase free tier.
    Первичный keepalive — GitHub Actions (supabase_ping.yml).

    Логика: один раз в день по session_state['last_keepalive_date'].
    Ping: INSERT в health_ping с datetime.now(timezone.utc).isoformat().
    При ошибке: log_warning(), НЕ raise, НЕ st.error().

    Вызывать: только в auth_callback.py после verify_magic_link().
    Spec ref: Section 11.
    """
    last_date: date | None = st.session_state.get("last_keepalive_date")
    today: date = date.today()

    # Сегодня уже делали ping — пропускаем
    if last_date == today:
        return

    try:
        client: Client = _get_supabase_client()

        # Section 11: использовать isoformat(), НЕ строку 'NOW()'
        ping_timestamp: str = datetime.now(timezone.utc).isoformat()

        client.table("health_ping").insert({
            "pinged_at": ping_timestamp,
            "source": "app_keepalive",
            "user": user_email,
        }).execute()

        st.session_state["last_keepalive_date"] = today

        # Section 19: email — PII, не логируем через log_info
        log_info("keep_alive_ping_success", extra={"date": str(today)})

    except Exception as exc:
        # Section 11: не показывать пользователю, только log_warning
        log_warning(
            "keep_alive_ping_failed",
            extra={"email": user_email, "error": str(exc)},
        )
