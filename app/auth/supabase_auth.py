"""
auth/supabase_auth.py
SubAudit — Master Specification Sheet v2.9
Раздел: Section 12 (Authentication), Section 11 (keep_alive_if_needed),
        Section 16 Step 6 (Development Order)

Функции:
  - send_magic_link(email: str) -> bool
  - verify_magic_link(token: str) -> dict or None
  - get_user_plan(user_email: str) -> 'free' | 'starter' | 'pro'
  - keep_alive_if_needed(user_email: str) -> None
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone

import streamlit as st
from supabase import create_client, Client

from app.observability.logger import log_error, log_warning, log_info

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

# Section 11: COOLDOWN используется в 7_account.py для ограничения повторной
# отправки magic link. Отдельная константа — не связана с логикой keepalive.
COOLDOWN: int = 60  # секунды

# ---------------------------------------------------------------------------
# Инициализация клиента Supabase
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Client:
    """
    Создаёт и возвращает клиент Supabase.
    Ключи хранятся ТОЛЬКО в Streamlit Secrets (Section 19 — Pre-launch Checklist).
    Никогда не хранить ключи в коде или .env, попавших в репозиторий.
    """
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
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

    Spec ref: Section 12, таблица функций аутентификации.
    Cooldown (60 сек) применяется на уровне 7_account.py — не здесь.
    """
    try:
        client: Client = _get_supabase_client()
        # Supabase GoTrue: signInWithOtp отправляет magic link на email
        client.auth.sign_in_with_otp({"email": email})
        log_info("magic_link_sent", {"email": email})
        return True
    except Exception as exc:
        log_error("send_magic_link_failed", exc, {"email": email})
        return False


# ---------------------------------------------------------------------------
# verify_magic_link — Section 12
# ---------------------------------------------------------------------------

def verify_magic_link(token: str) -> dict | None:
    """
    Верифицирует токен magic link и возвращает словарь с данными пользователя.

    Параметры:
        token (str): токен из URL magic link (обычно получается в auth_callback.py)

    Возвращает:
        dict с ключами {'email': str, ...} или None при ошибке верификации

    Spec ref: Section 12.
    ВАЖНО: keep_alive_if_needed() НЕ вызывается внутри этой функции.
    Вызов keep_alive_if_needed() производится ПОСЛЕ успешной верификации
    в auth_callback.py (Section 11 — "When to call").
    """
    try:
        client: Client = _get_supabase_client()
        # Верифицируем OTP-токен типа 'magiclink'
        response = client.auth.verify_otp({"token_hash": token, "type": "magiclink"})

        if response and response.user:
            user_dict = {
                "email": response.user.email,
                "id": response.user.id,
                "user_metadata": response.user.user_metadata,
            }
            log_info("verify_magic_link_success", {"email": response.user.email})
            return user_dict

        # Supabase вернул ответ без пользователя — токен невалиден
        log_warning("verify_magic_link_no_user", {"token_prefix": token[:8]})
        return None

    except Exception as exc:
        log_error("verify_magic_link_failed", exc, {"token_prefix": token[:8]})
        return None


# ---------------------------------------------------------------------------
# get_user_plan — Section 12
# ---------------------------------------------------------------------------

def get_user_plan(user_email: str) -> str:
    """
    Возвращает план пользователя из Supabase.
    Используется как FALLBACK — основным источником истины является
    Lemon Squeezy (app/payments/lemon_squeezy.py).

    Параметры:
        user_email (str): email пользователя

    Возвращает:
        str: 'free' | 'starter' | 'pro'

    Spec ref: Section 12, таблица функций.
    """
    try:
        client: Client = _get_supabase_client()
        # Таблица user_plans хранит актуальный план после webhook от Lemon Squeezy
        response = (
            client
            .table("user_plans")
            .select("plan")
            .eq("email", user_email)
            .single()
            .execute()
        )

        plan = response.data.get("plan", "free") if response.data else "free"

        # Валидация: допустимы только три значения (Section 2 — Pricing Plans)
        if plan not in ("free", "starter", "pro"):
            log_warning("get_user_plan_invalid_value", {"email": user_email, "plan": plan})
            return "free"

        return plan

    except Exception as exc:
        log_error("get_user_plan_failed", exc, {"email": user_email})
        # Безопасный fallback — 'free' (Section 13 аналогичная логика для LS)
        return "free"


# ---------------------------------------------------------------------------
# keep_alive_if_needed — Section 11 (полная спецификация)
# ---------------------------------------------------------------------------

def keep_alive_if_needed(user_email: str) -> None:
    """
    Вторичный keepalive для предотвращения паузы Supabase free tier.
    Первичный keepalive — GitHub Actions (.github/workflows/supabase_ping.yml).

    Логика "один раз в день":
        Сравниваем session_state['last_keepalive_date'] с date.today().
        Если даты различаются ИЛИ ключ отсутствует → выполняем ping.
        Если даты совпадают → пропускаем (Section 11 — "Once per day" condition).

    Операция ping:
        INSERT в таблицу health_ping.
        Значение времени: datetime.now(timezone.utc).isoformat()
        НЕ использовать строку 'NOW()' — Section 11, Ping operation.

    При ошибке:
        log_warning() через logger.py. НЕ raise. НЕ показывать UI ошибку.
        Section 11: "On failure — Do NOT raise. Do NOT show UI error."

    Когда вызывать:
        Только в auth_callback.py ПОСЛЕ успешного verify_magic_link().
        НЕ внутри verify_magic_link() — Section 11, "When to call".

    Параметры:
        user_email (str): email вошедшего пользователя (для логирования)

    Возвращает:
        None
    """
    # --- Проверка условия "один раз в день" ---
    last_date: date | None = st.session_state.get("last_keepalive_date")
    today: date = date.today()

    if last_date == today:
        # Сегодня уже выполняли ping — пропускаем
        return

    # --- Выполняем ping ---
    try:
        client: Client = _get_supabase_client()

        # Используем isoformat() — НЕ строку 'NOW()' (Section 11)
        ping_timestamp: str = datetime.now(timezone.utc).isoformat()

        client.table("health_ping").insert(
            {"pinged_at": ping_timestamp, "source": "app_keepalive", "user": user_email}
        ).execute()

        # Обновляем дату последнего keepalive в session_state
        st.session_state["last_keepalive_date"] = today

        log_info("keep_alive_ping_success", {"email": user_email, "date": str(today)})

    except Exception as exc:
        # Section 11: ошибка keepalive не является пользовательской — только логируем
        log_warning(
            "keep_alive_ping_failed",
            {"email": user_email, "error": str(exc)},
        )
        # НЕ raise, НЕ показывать st.error() — пользователь не должен видеть это
