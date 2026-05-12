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
        # Получаем клиент Supabase через модульный атрибут
        # (тесты могут мокировать app.auth.supabase_auth.supabase)
        from app.auth.supabase_auth import _client
        client: Client = _client()

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
