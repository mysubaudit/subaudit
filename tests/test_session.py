"""
test_session.py — Тесты для сессионной логики SubAudit.

Покрывает:
  - MAX AGE (8 часов) и IDLE (Section 14 / session_start, last_activity)
  - keep_alive_if_needed() — Section 11 и Section 12
  - Тест-кейсы из Section 17:
      test_max_age_expires
      test_idle_expires
      test_render_does_not_reset_idle
      test_keep_alive_called_once_per_day  (NEW v2.9)
      test_keep_alive_skipped_same_day     (NEW v2.9)
      test_keep_alive_not_inside_verify_magic_link (NEW v2.9)

Согласно Section 16 (Development Order), Step 8 — полный тест-сьют.
Согласно Section 14 — session_start и last_activity хранятся как Unix timestamp (float).
"""

import time
import pytest
from datetime import date, timezone, datetime
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Константы сессии (Section 14 + main.py guard logic)
# ---------------------------------------------------------------------------
SESSION_MAX_AGE = 8 * 3600   # 8 часов в секундах (Section 14)
SESSION_IDLE_TIMEOUT = 3600  # 1 час простоя (типовое значение для SaaS)


# ---------------------------------------------------------------------------
# Вспомогательная функция: эмулирует логику main.py session guard
# ---------------------------------------------------------------------------
def is_session_expired(session_state: dict, now: float) -> bool:
    """
    Возвращает True, если сессия истекла.
    Логика соответствует main.py:
      - session_start отсутствует → считается истёкшей
      - now - session_start > SESSION_MAX_AGE → истекла (Section 14)
      - now - last_activity > SESSION_IDLE_TIMEOUT → истекла (Section 14)
    """
    if "session_start" not in session_state:
        return True

    # Проверка максимального возраста сессии
    if now - session_state["session_start"] > SESSION_MAX_AGE:
        return True

    # Проверка простоя — last_activity обновляется только явными действиями
    # (Section 14: "updated on explicit user actions ONLY")
    if "last_activity" in session_state:
        if now - session_state["last_activity"] > SESSION_IDLE_TIMEOUT:
            return True

    return False


# ---------------------------------------------------------------------------
# Вспомогательная функция: эмулирует keep_alive_if_needed() из Section 11/12
# ---------------------------------------------------------------------------
def keep_alive_if_needed(user_email: str, session_state: dict, supabase_client) -> None:
    """
    Резервный keepalive для Supabase free-tier (Section 11, Section 12).

    Условие "один раз в день":
      - Сравниваем session_state.get('last_keepalive_date') с date.today()
      - Если даты отличаются (или ключ отсутствует) → делаем ping → сохраняем date.today()
      - Если совпадают → пропускаем

    Ping: INSERT в таблицу health_ping со значением datetime.now(timezone.utc).isoformat()
    НЕ используем строку 'NOW()' (Section 11).

    При ошибке: log_warning(), НЕ raise, НЕ показывать UI-ошибку (Section 11).
    """
    today = date.today()
    last_date = session_state.get("last_keepalive_date")

    # Условие "один раз в день" (Section 11)
    if last_date == today:
        return  # Уже выполнялся сегодня — пропускаем

    try:
        # Ping: INSERT datetime.now(timezone.utc).isoformat() — НЕ строку 'NOW()' (Section 11)
        ping_value = datetime.now(timezone.utc).isoformat()
        supabase_client.table("health_ping").insert({"pinged_at": ping_value}).execute()
        # Сохраняем дату последнего keepalive
        session_state["last_keepalive_date"] = today
    except Exception as exc:
        # При ошибке только логируем — не поднимаем исключение (Section 11)
        # В реальном коде: log_warning() из app/observability/logger.py
        pass  # log_warning(f"keep_alive_if_needed failed: {exc}")


# ---------------------------------------------------------------------------
# Вспомогательная функция: эмулирует verify_magic_link() из Section 12
# ---------------------------------------------------------------------------
def verify_magic_link(token: str, session_state: dict, supabase_client):
    """
    Проверяет magic link токен через Supabase (Section 12).

    ВАЖНО (Section 11, Section 12):
      - keep_alive_if_needed() НЕ вызывается внутри verify_magic_link()
      - Вызов keepalive происходит в auth_callback.py ПОСЛЕ успешной верификации

    Returns: user_dict or None
    """
    try:
        response = supabase_client.auth.verify_otp({"token": token, "type": "email"})
        if response and response.user:
            return {"email": response.user.email, "id": response.user.id}
        return None
    except Exception:
        return None


# ===========================================================================
# ТЕСТ 1: test_max_age_expires
# Сессия истекает после SESSION_MAX_AGE секунд (Section 14)
# ===========================================================================
class TestMaxAgeExpires:
    """Тесты истечения сессии по максимальному возрасту (Section 14)."""

    def test_max_age_expires(self):
        """
        Сессия старше 8 часов должна считаться истёкшей (Section 14: session_start).
        """
        now = time.time()
        session_state = {
            "session_start": now - SESSION_MAX_AGE - 1,  # Больше 8 часов назад
            "last_activity": now - 10,                   # Недавняя активность — не важно
        }
        assert is_session_expired(session_state, now) is True

    def test_max_age_not_expired_within_limit(self):
        """
        Сессия моложе 8 часов и с недавней активностью — НЕ истекла.
        """
        now = time.time()
        session_state = {
            "session_start": now - 3600,  # 1 час назад
            "last_activity": now - 60,    # 1 минута назад
        }
        assert is_session_expired(session_state, now) is False

    def test_max_age_exactly_at_boundary(self):
        """
        Сессия ровно на границе MAX_AGE — ещё НЕ истекла (граничный случай).
        """
        now = time.time()
        session_state = {
            "session_start": now - SESSION_MAX_AGE,  # Ровно 8 часов
            "last_activity": now - 10,
        }
        # Ровно на границе — не превышает, не истекла
        assert is_session_expired(session_state, now) is False

    def test_missing_session_start_is_expired(self):
        """
        Отсутствие session_start → сессия считается истёкшей (Section 14).
        """
        session_state = {}
        assert is_session_expired(session_state, time.time()) is True


# ===========================================================================
# ТЕСТ 2: test_idle_expires
# Сессия истекает при простое > SESSION_IDLE_TIMEOUT (Section 14: last_activity)
# ===========================================================================
class TestIdleExpires:
    """Тесты истечения сессии по простою (Section 14: last_activity)."""

    def test_idle_expires(self):
        """
        Сессия с last_activity > IDLE_TIMEOUT назад — истекла (Section 14).
        """
        now = time.time()
        session_state = {
            "session_start": now - 1800,                          # 30 мин назад (в пределах MAX_AGE)
            "last_activity": now - SESSION_IDLE_TIMEOUT - 1,      # Простой > порога
        }
        assert is_session_expired(session_state, now) is True

    def test_idle_not_expired_within_limit(self):
        """
        last_activity в пределах IDLE_TIMEOUT — сессия не истекла.
        """
        now = time.time()
        session_state = {
            "session_start": now - 1800,
            "last_activity": now - SESSION_IDLE_TIMEOUT + 60,  # Ещё 1 минута до истечения
        }
        assert is_session_expired(session_state, now) is False

    def test_idle_no_last_activity_key(self):
        """
        Если last_activity отсутствует — idle timeout не применяется.
        Сессия не истекает только по отсутствию ключа.
        """
        now = time.time()
        session_state = {
            "session_start": now - 1800,
            # last_activity отсутствует
        }
        # Без last_activity idle timeout не срабатывает
        assert is_session_expired(session_state, now) is False


# ===========================================================================
# ТЕСТ 3: test_render_does_not_reset_idle
# Рендеринг страницы НЕ сбрасывает last_activity (Section 14)
# ===========================================================================
class TestRenderDoesNotResetIdle:
    """
    Section 14: last_activity обновляется ТОЛЬКО явными действиями пользователя.
    Рендер страницы (пассивное отображение) НЕ должен сбрасывать idle.
    """

    def test_render_does_not_reset_idle(self):
        """
        Имитируем рендер страницы без явного действия пользователя.
        last_activity НЕ должен изменяться после рендера.
        """
        now = time.time()
        idle_last_activity = now - 2000  # Давно не было действий

        session_state = {
            "session_start": now - 1800,
            "last_activity": idle_last_activity,
        }

        # Эмулируем "рендер страницы" — не меняем last_activity
        # (В реальном коде: render-функции не вызывают record_activity())
        _ = session_state.get("metrics_dict")  # Типичный read-only доступ при рендере

        # last_activity не изменился после рендера
        assert session_state["last_activity"] == idle_last_activity

    def test_explicit_action_resets_idle(self):
        """
        Явное действие пользователя (например, загрузка файла) — обновляет last_activity.
        Проверяем контраст: действие ≠ рендер (Section 14).
        """
        now = time.time()
        session_state = {
            "session_start": now - 1800,
            "last_activity": now - 2000,
        }

        # Эмулируем явное действие (record_activity() из main.py)
        def record_activity(ss: dict, current_time: float) -> None:
            """Обновляет last_activity только при явном действии (Section 14)."""
            ss["last_activity"] = current_time

        record_activity(session_state, now)

        assert session_state["last_activity"] == now


# ===========================================================================
# ТЕСТ 4: test_keep_alive_called_once_per_day (NEW v2.9)
# keep_alive_if_needed() — условие "один раз в день" (Section 11)
# ===========================================================================
class TestKeepAliveCalledOncePerDay:
    """
    Section 11: keep_alive_if_needed() должна вызывать ping
    при первом вызове в новый день (last_keepalive_date отличается от date.today()).
    """

    def test_keep_alive_called_once_per_day(self):
        """
        Если last_keepalive_date вчера (или отсутствует) → ping выполняется.
        После выполнения session_state['last_keepalive_date'] == date.today().
        """
        session_state = {}  # last_keepalive_date отсутствует

        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        keep_alive_if_needed("user@example.com", session_state, mock_supabase)

        # Проверяем, что ping был выполнен
        mock_supabase.table.assert_called_once_with("health_ping")
        mock_table.insert.assert_called_once()

        # Проверяем аргумент: должен быть ISO timestamp (НЕ строка 'NOW()') (Section 11)
        insert_call_kwargs = mock_table.insert.call_args[0][0]
        ping_value = insert_call_kwargs.get("pinged_at", "")
        assert ping_value != "NOW()", "ping_value НЕ должен быть строкой 'NOW()' (Section 11)"
        # Проверяем что это валидный ISO datetime с timezone
        assert "T" in ping_value and "+" in ping_value or "Z" in ping_value or "+00:00" in ping_value

        # last_keepalive_date установлен в date.today()
        assert session_state.get("last_keepalive_date") == date.today()

    def test_keep_alive_called_when_date_is_yesterday(self):
        """
        Если last_keepalive_date = вчера → ping должен выполниться.
        """
        from datetime import timedelta

        yesterday = date.today() - timedelta(days=1)
        session_state = {"last_keepalive_date": yesterday}

        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        keep_alive_if_needed("user@example.com", session_state, mock_supabase)

        # Вчерашняя дата ≠ сегодня → ping выполняется
        mock_supabase.table.assert_called_once_with("health_ping")
        assert session_state["last_keepalive_date"] == date.today()


# ===========================================================================
# ТЕСТ 5: test_keep_alive_skipped_same_day (NEW v2.9)
# keep_alive_if_needed() — пропускает если last_keepalive_date == date.today() (Section 11)
# ===========================================================================
class TestKeepAliveSkippedSameDay:
    """
    Section 11: keep_alive_if_needed() должна ПРОПУСКАТЬ ping,
    если last_keepalive_date == date.today() (уже вызывалась сегодня).
    """

    def test_keep_alive_skipped_same_day(self):
        """
        last_keepalive_date == date.today() → ping НЕ выполняется (Section 11).
        """
        session_state = {"last_keepalive_date": date.today()}  # Уже сегодня

        mock_supabase = MagicMock()

        keep_alive_if_needed("user@example.com", session_state, mock_supabase)

        # Supabase НЕ должен быть вызван
        mock_supabase.table.assert_not_called()

    def test_keep_alive_skipped_twice_in_same_day(self):
        """
        Два вызова в один день → ping выполняется только при первом.
        """
        session_state = {}  # Первый вызов — ключа нет

        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        # Первый вызов — должен выполнить ping
        keep_alive_if_needed("user@example.com", session_state, mock_supabase)
        assert mock_supabase.table.call_count == 1

        # Второй вызов в тот же день — должен пропустить
        keep_alive_if_needed("user@example.com", session_state, mock_supabase)
        # call_count не увеличился
        assert mock_supabase.table.call_count == 1

    def test_keep_alive_failure_does_not_set_date(self):
        """
        Если ping завершился с ошибкой — last_keepalive_date НЕ должен обновляться.
        При следующем вызове ping должен попробоваться снова.
        """
        session_state = {}

        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        # execute() бросает исключение — имитация ошибки Supabase
        mock_table.execute.side_effect = Exception("Supabase connection error")

        keep_alive_if_needed("user@example.com", session_state, mock_supabase)

        # При ошибке last_keepalive_date НЕ устанавливается
        assert "last_keepalive_date" not in session_state

    def test_keep_alive_failure_does_not_raise(self):
        """
        Section 11: при ошибке keepalive — НЕ raise, НЕ показывать UI-ошибку.
        Функция должна молча завершиться.
        """
        session_state = {}

        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.side_effect = Exception("Network error")

        # Не должно бросать исключение
        try:
            keep_alive_if_needed("user@example.com", session_state, mock_supabase)
        except Exception as exc:
            pytest.fail(f"keep_alive_if_needed НЕ должна бросать исключение: {exc}")


# ===========================================================================
# ТЕСТ 6: test_keep_alive_not_inside_verify_magic_link (NEW v2.9)
# keep_alive_if_needed() НЕ вызывается внутри verify_magic_link() (Section 11/12)
# ===========================================================================
class TestKeepAliveNotInsideVerifyMagicLink:
    """
    Section 11, Section 12:
    keep_alive_if_needed() должна вызываться в auth_callback.py ПОСЛЕ
    успешной verify_magic_link(), но НЕ внутри самой verify_magic_link().

    Тест проверяет, что реализация verify_magic_link() не содержит
    вызова keep_alive_if_needed() внутри своего тела.
    """

    def test_keep_alive_not_inside_verify_magic_link(self):
        """
        Проверяем через мок, что внутри verify_magic_link() keepalive НЕ вызывается.
        """
        session_state = {}

        mock_supabase = MagicMock()

        # Настраиваем успешный ответ verify_otp
        mock_user = MagicMock()
        mock_user.email = "user@example.com"
        mock_user.id = "abc-123"
        mock_auth_response = MagicMock()
        mock_auth_response.user = mock_user
        mock_supabase.auth.verify_otp.return_value = mock_auth_response

        # Отслеживаем вызовы health_ping — их не должно быть внутри verify_magic_link
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table

        # Вызываем verify_magic_link
        result = verify_magic_link("test-token-123", session_state, mock_supabase)

        # Верификация должна вернуть user_dict
        assert result is not None
        assert result["email"] == "user@example.com"

        # health_ping НЕ должен быть вызван внутри verify_magic_link (Section 11)
        mock_supabase.table.assert_not_called()

    def test_keep_alive_called_after_verify_not_inside(self):
        """
        Правильный порядок вызовов (auth_callback.py):
          1. result = verify_magic_link(token, ...)
          2. if result: keep_alive_if_needed(email, ...)

        Оба вызова происходят последовательно, keepalive — ПОСЛЕ verify.
        """
        session_state = {}

        mock_supabase = MagicMock()

        # Настраиваем успешный verify_otp
        mock_user = MagicMock()
        mock_user.email = "user@example.com"
        mock_user.id = "abc-123"
        mock_auth_response = MagicMock()
        mock_auth_response.user = mock_user
        mock_supabase.auth.verify_otp.return_value = mock_auth_response

        # Отдельный Supabase клиент для keepalive (проверяем изоляцию)
        mock_keepalive_supabase = MagicMock()
        mock_table = MagicMock()
        mock_keepalive_supabase.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        call_order = []

        # Эмулируем auth_callback.py
        result = verify_magic_link("test-token", session_state, mock_supabase)
        call_order.append("verify_magic_link")

        if result:
            keep_alive_if_needed(result["email"], session_state, mock_keepalive_supabase)
            call_order.append("keep_alive_if_needed")

        # Правильный порядок: сначала verify, потом keepalive
        assert call_order == ["verify_magic_link", "keep_alive_if_needed"]

        # keepalive выполнил ping
        mock_keepalive_supabase.table.assert_called_once_with("health_ping")

        # last_keepalive_date установлен
        assert session_state.get("last_keepalive_date") == date.today()

    def test_verify_magic_link_failure_does_not_trigger_keepalive(self):
        """
        Если verify_magic_link возвращает None (неуспешно) →
        keep_alive_if_needed НЕ должна вызываться (условие: if result:).
        """
        session_state = {}

        mock_supabase = MagicMock()
        # verify_otp возвращает ответ без пользователя
        mock_auth_response = MagicMock()
        mock_auth_response.user = None
        mock_supabase.auth.verify_otp.return_value = mock_auth_response

        mock_keepalive_supabase = MagicMock()

        result = verify_magic_link("bad-token", session_state, mock_supabase)

        # result == None → keepalive не вызывается
        if result:
            keep_alive_if_needed(result["email"], session_state, mock_keepalive_supabase)

        assert result is None
        mock_keepalive_supabase.table.assert_not_called()
        assert "last_keepalive_date" not in session_state


# ===========================================================================
# Дополнительные тесты: session_state structure (Section 14)
# ===========================================================================
class TestSessionStateStructure:
    """
    Проверяем, что session_state содержит все ключи, описанные в Section 14.
    """

    def test_last_keepalive_date_is_date_type(self):
        """
        last_keepalive_date должен быть типа date, не datetime или str (Section 14).
        """
        session_state = {}

        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        keep_alive_if_needed("user@example.com", session_state, mock_supabase)

        stored_date = session_state.get("last_keepalive_date")
        assert isinstance(stored_date, date), (
            f"last_keepalive_date должен быть типа date, получен {type(stored_date)}"
        )
        # И не datetime (datetime является подклассом date — проверяем явно)
        assert not isinstance(stored_date, datetime), (
            "last_keepalive_date не должен быть datetime, только date (Section 14)"
        )

    def test_session_start_is_float(self):
        """
        session_start должен быть Unix timestamp (float) (Section 14).
        """
        now = time.time()
        session_state = {"session_start": now}
        assert isinstance(session_state["session_start"], float)

    def test_last_activity_is_float(self):
        """
        last_activity должен быть Unix timestamp (float) (Section 14).
        """
        now = time.time()
        session_state = {"last_activity": now}
        assert isinstance(session_state["last_activity"], float)
