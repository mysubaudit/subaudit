"""
core/feedback.py
SubAudit — Master Specification Sheet v2.9
Раздел: Section 15 (User Feedback)

Функция для отправки отзывов пользователей в Supabase.
Вызывается из 7_account.py при клике на кнопку "Send Feedback".
"""

from __future__ import annotations

import streamlit as st
from supabase import Client

from app.observability.logger import log_error, log_info


def send_feedback(user_email: str, rating: int | None, message: str) -> bool:
    """
    Отправляет отзыв пользователя в таблицу feedback в Supabase.

    Параметры:
        user_email (str): email пользователя (из session_state)
        rating (int | None): рейтинг 1-5 звёзд (None если не выбран)
        message (str): текстовое сообщение (может быть пустым)

    Возвращает:
        bool: True — отзыв успешно сохранён, False — произошла ошибка

    Spec ref: Section 15 (User Feedback).
    """
    # Валидация: хотя бы рейтинг или сообщение должны быть заполнены
    if rating is None and not message.strip():
        return False

    try:
        # Для операций с feedback используем service_role_key (обходит RLS)
        # Это безопасно, потому что:
        # 1. Проверка авторизации уже сделана в 7_account.py
        # 2. Email берётся из session_state (установлен при входе)
        # 3. Пользователь не может подделать чужой email

        import streamlit as st
        from supabase import create_client, Client

        # Получаем credentials из secrets (поддержка обоих форматов)
        if "supabase" in st.secrets:
            # Формат А: секция [supabase]
            url = st.secrets["supabase"]["url"]
            key = (
                st.secrets["supabase"].get("service_role_key")
                or st.secrets["supabase"].get("anon_key")
                or st.secrets["supabase"].get("key")
            )
        else:
            # Формат Б: плоские ключи (текущий формат проекта)
            url = st.secrets["SUPABASE_URL"]
            key = (
                st.secrets.get("SUPABASE_SERVICE_ROLE_KEY")
                or st.secrets.get("SUPABASE_ANON_KEY")
                or st.secrets.get("SUPABASE_KEY")
            )

        if not url or not key:
            raise ValueError("Supabase credentials not found in secrets")

        # Создаём отдельный клиент для feedback (не используем глобальный)
        client: Client = create_client(url, key)

        # Подготовка данных для вставки
        feedback_data = {
            "user_email": user_email,
            "rating": rating,
            "message": message.strip() if message else None,
        }

        # Вставка в таблицу feedback
        client.table("feedback").insert(feedback_data).execute()

        # Section 19: email — PII, не логируем через log_info
        log_info("feedback_sent", extra={"has_rating": rating is not None, "has_message": bool(message)})
        return True

    except Exception as exc:
        log_error(
            "send_feedback_failed",
            exc=exc,
            extra={
                "email": user_email,
                "exc_type": type(exc).__name__,
                "exc_detail": str(exc),
            },
        )
        return False
