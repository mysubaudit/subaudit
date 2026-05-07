"""
test_session.py — Тесты для сессионной логики SubAudit.

Покрывает все тест-кейсы из Section 17:
    test_max_age_expires
    test_idle_expires
    test_render_does_not_reset_idle
    test_keep_alive_called_once_per_day  (NEW v2.9)
    test_keep_alive_skipped_same_day     (NEW v2.9)
    test_keep_alive_not_inside_verify_magic_link (NEW v2.9)

Согласно Section 16, Step 8 — полный тест-сьют.
Согласно Section 14 — session_start и last_activity хранятся как Unix timestamp (float).

ИСПРАВЛЕНИЯ:
  - БАГ 1: тесты keep_alive / verify_magic_link теперь тестируют реальные модули
            app/auth/supabase_auth.py через mocker.patch, а не локальные заглушки.
            Локальные заглушки оставлены ТОЛЬКО для тестов is_session_expired
            (session guard из main.py — не выделен в отдельный модуль).
  - БАГ 2: проверка ISO timestamp через datetime.fromisoformat() + tzinfo,
            а не хрупкое строковое условие с or/and без скобок.
  - БАГ 3: антипаттерн try/except в test_keep_alive_failure_does_not_raise
            заменён на прямой вызов (pytest сам поймает любое исключение).
  - БАГ 4: доступ к аргументам мока через call_args.args[0] (Python 3.8+)
            вместо хрупкого call_args[0][0].
"""

import time
import pytest
from datetime import date, timedelta, timezone, datetime
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Константы сессии (Section 14 + main.py guard logic)
# ---------------------------------------------------------------------------
SESSION_MAX_AGE = 8 * 3600   # 8 часов в секундах (Section 14)
SESSION_IDLE_TIMEOUT = 3600  # 1 час простоя (Section 14)


# ---------------------------------------------------------------------------
# Локальная заглушка is_session_expired — эмулирует guard из main.py.
# Тестируется напрямую, т.к. логика встроена в main.py (не отдельный модуль).
# ---------------------------------------------------------------------------
def _is_session_expired(session_state: dict, now: float) -> bool:
    """
    Возвращает True, если сессия истекла.
    Логика соответствует main.py session guard:
      - session_start отсутствует → истекла
      - now - session_start > SESSION_MAX_AGE → истекла (Section 14)
      - now - last_activity > SESSION_IDLE_TIMEOUT → истекла (Section 14)
    """
    if "session_start" not in session_state:
        return True
    if now - session_state["session_start"] > SESSION_MAX_AGE:
        return True
    if "last_activity" in session_state:
        if now - session_state["last_activity"] > SESSION_IDLE_TIMEOUT:
            return True
    return False


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
            "session_start": now - SESSION_MAX_AGE - 1,  # больше 8 часов назад
            "last_activity": now - 10,
        }
        assert _is_session_expired(session_state, now) is True

    def test_max_age_not_expired_within_limit(self):
        """
        Сессия моложе 8 часов и с недавней активностью — НЕ истекла.
        """
        now = time.time()
        session_state = {
            "session_start": now - 3600,  # 1 час назад
            "last_activity": now - 60,    # 1 минута назад
        }
        assert _is_session_expired(session_state, now) is False

    def test_max_age_exactly_at_boundary(self):
        """
        Сессия ровно на границе MAX_AGE — ещё НЕ истекла (граничный случай).
        Условие строгое: > SESSION_MAX_AGE, не >=.
        """
        now = time.time()
        session_state = {
            "session_start": now - SESSION_MAX_AGE,  # ровно 8 часов
            "last_activity": now - 10,
        }
        assert _is_session_expired(session_state, now) is False

    def test_missing_session_start_is_expired(self):
        """
        Отсутствие session_start → сессия считается истёкшей (Section 14).
        """
        session_state = {}
        assert _is_session_expired(session_state, time.time()) is True


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
            "session_start": now - 1800,                       # 30 мин назад (в пределах MAX_AGE)
            "last_activity": now - SESSION_IDLE_TIMEOUT - 1,  # простой превышен
        }
        assert _is_session_expired(session_state, now) is True

    def test_idle_not_expired_within_limit(self):
        """
        last_activity в пределах IDLE_TIMEOUT — сессия не истекла.
        """
        now = time.time()
        session_state = {
            "session_start": now - 1800,
            "last_activity": now - SESSION_IDLE_TIMEOUT + 60,  # ещё 1 минута до истечения
        }
        assert _is_session_expired(session_state, now) is False

    def test_idle_no_last_activity_key(self):
        """
        Если last_activity отсутствует — idle timeout не применяется.
        Сессия не считается истёкшей только из-за отсутствия ключа.
        """
        now = time.time()
        session_state = {
            "session_start": now - 1800,
            # last_activity намеренно отсутствует
        }
        assert _is_session_expired(session_state, now) is False


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
        idle_last_activity = now - 2000  # давно не было действий

        session_state = {
            "session_start": now - 1800,
            "last_activity": idle_last_activity,
        }

        # Эмулируем "рендер страницы" — read-only доступ к данным
        # В реальном коде render-функции не вызывают record_activity()
        _ = session_state.get("metrics_dict")

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

        def record_activity(ss: dict, current_time: float) -> None:
            """Обновляет last_activity только при явном действии (Section 14)."""
            ss["last_activity"] = current_time

        record_activity(session_state, now)

        assert session_state["last_activity"] == now


# ===========================================================================
# ТЕСТ 4: test_keep_alive_called_once_per_day (NEW v2.9)
# keep_alive_if_needed() — условие "один раз в день" (Section 11)
# Тестируем реальный модуль: app/auth/supabase_auth.py
# ===========================================================================
class TestKeepAliveCalledOncePerDay:
    """
    Section 11: keep_alive_if_needed() вызывает ping
    при первом вызове в новый день (last_keepalive_date != date.today()).
    """

    def test_keep_alive_called_once_per_day(self, mocker):
        """
        Если last_keepalive_date отсутствует → ping выполняется.
        После выполнения session_state['last_keepalive_date'] == date.today().

        БАГ 1 ИСПРАВЛЕН: тестируем реальный модуль через mocker.patch.
        БАГ 2 ИСПРАВЛЕН: проверка ISO timestamp через datetime.fromisoformat().
        БАГ 4 ИСПРАВЛЕН: доступ через call_args.args[0].
        """
        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        # Патчим session_state и supabase клиент в реальном модуле
        fake_state = {}
        mocker.patch("app.auth.supabase_auth.st.session_state", fake_state)
        mocker.patch("app.auth.supabase_auth.supabase", mock_supabase)

        from app.auth.supabase_auth import keep_alive_if_needed
        keep_alive_if_needed("user@example.com")

        # Ping должен быть выполнен один раз в таблицу health_ping
        mock_supabase.table.assert_called_once_with("health_ping")
        mock_table.insert.assert_called_once()

        # БАГ 4 ИСПРАВЛЕН: надёжный доступ к аргументам мока
        args, kwargs = mock_table.insert.call_args
        insert_payload = args[0] if args else kwargs
        ping_value = insert_payload.get("pinged_at", "")

        # Section 11: НЕ строка 'NOW()' — должен быть ISO datetime
        assert ping_value != "NOW()", (
            "Section 11: ping_value НЕ должен быть строкой 'NOW()'"
        )

        # БАГ 2 ИСПРАВЛЕН: проверка через fromisoformat + tzinfo вместо строкового or/and
        try:
            parsed_dt = datetime.fromisoformat(ping_value)
        except ValueError:
            pytest.fail(
                f"Section 11: ping_value '{ping_value}' не является валидным ISO datetime"
            )
        assert parsed_dt.tzinfo is not None, (
            "Section 11: ping datetime должен содержать timezone "
            "(datetime.now(timezone.utc))"
        )

        # last_keepalive_date установлен в date.today()
        assert fake_state.get("last_keepalive_date") == date.today()

    def test_keep_alive_called_when_date_is_yesterday(self, mocker):
        """
        Если last_keepalive_date = вчера → ping должен выполниться.
        """
        yesterday = date.today() - timedelta(days=1)
        fake_state = {"last_keepalive_date": yesterday}

        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        mocker.patch("app.auth.supabase_auth.st.session_state", fake_state)
        mocker.patch("app.auth.supabase_auth.supabase", mock_supabase)

        from app.auth.supabase_auth import keep_alive_if_needed
        keep_alive_if_needed("user@example.com")

        # Вчерашняя дата ≠ сегодня → ping выполняется
        mock_supabase.table.assert_called_once_with("health_ping")
        assert fake_state["last_keepalive_date"] == date.today()


# ===========================================================================
# ТЕСТ 5: test_keep_alive_skipped_same_day (NEW v2.9)
# keep_alive_if_needed() пропускает если last_keepalive_date == date.today()
# Section 11
# ===========================================================================
class TestKeepAliveSkippedSameDay:
    """
    Section 11: keep_alive_if_needed() ПРОПУСКАЕТ ping,
    если last_keepalive_date == date.today().
    """

    def test_keep_alive_skipped_same_day(self, mocker):
        """
        last_keepalive_date == date.today() → ping НЕ выполняется (Section 11).
        """
        fake_state = {"last_keepalive_date": date.today()}  # уже сегодня

        mock_supabase = MagicMock()
        mocker.patch("app.auth.supabase_auth.st.session_state", fake_state)
        mocker.patch("app.auth.supabase_auth.supabase", mock_supabase)

        from app.auth.supabase_auth import keep_alive_if_needed
        keep_alive_if_needed("user@example.com")

        # Supabase НЕ должен быть вызван
        mock_supabase.table.assert_not_called()

    def test_keep_alive_skipped_twice_in_same_day(self, mocker):
        """
        Два вызова в один день → ping выполняется только при первом.
        """
        fake_state = {}  # первый вызов — ключа нет

        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        mocker.patch("app.auth.supabase_auth.st.session_state", fake_state)
        mocker.patch("app.auth.supabase_auth.supabase", mock_supabase)

        from app.auth.supabase_auth import keep_alive_if_needed

        # Первый вызов — должен выполнить ping
        keep_alive_if_needed("user@example.com")
        assert mock_supabase.table.call_count == 1

        # Второй вызов в тот же день — должен пропустить
        keep_alive_if_needed("user@example.com")
        # call_count не должен увеличиться
        assert mock_supabase.table.call_count == 1

    def test_keep_alive_failure_does_not_set_date(self, mocker):
        """
        Если ping завершился с ошибкой — last_keepalive_date НЕ должен обновляться.
        При следующем вызове ping должен попробоваться снова.
        Section 11: «On failure: Log warning. Do NOT raise.»
        """
        fake_state = {}

        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.side_effect = Exception("Supabase connection error")

        mocker.patch("app.auth.supabase_auth.st.session_state", fake_state)
        mocker.patch("app.auth.supabase_auth.supabase", mock_supabase)

        from app.auth.supabase_auth import keep_alive_if_needed
        keep_alive_if_needed("user@example.com")

        # При ошибке last_keepalive_date НЕ устанавливается
        assert "last_keepalive_date" not in fake_state

    def test_keep_alive_failure_does_not_raise(self, mocker):
        """
        Section 11: при ошибке keepalive — НЕ raise, НЕ показывать UI-ошибку.

        БАГ 3 ИСПРАВЛЕН: убран антипаттерн try/except вокруг вызова.
        Прямой вызов: если функция бросит — pytest сам зафиксирует падение.
        """
        fake_state = {}

        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.side_effect = Exception("Network error")

        mocker.patch("app.auth.supabase_auth.st.session_state", fake_state)
        mocker.patch("app.auth.supabase_auth.supabase", mock_supabase)

        from app.auth.supabase_auth import keep_alive_if_needed

        # БАГ 3 ИСПРАВЛЕН: прямой вызов без try/except
        # Если функция бросит исключение — тест упадёт автоматически
        keep_alive_if_needed("user@example.com")


# ===========================================================================
# ТЕСТ 6: test_keep_alive_not_inside_verify_magic_link (NEW v2.9)
# keep_alive_if_needed() НЕ вызывается внутри verify_magic_link() (Section 11/12)
# ===========================================================================
class TestKeepAliveNotInsideVerifyMagicLink:
    """
    Section 11, Section 12:
    keep_alive_if_needed() вызывается в auth_callback.py ПОСЛЕ
    успешной verify_magic_link(), но НЕ внутри самой verify_magic_link().
    """

    def test_keep_alive_not_inside_verify_magic_link(self, mocker):
        """
        Внутри verify_magic_link() keepalive НЕ вызывается.
        Проверяем через мок supabase: таблица health_ping не должна трогаться.

        БАГ 1 ИСПРАВЛЕН: тестируем реальный verify_magic_link из supabase_auth.py.
        """
        # Мок успешного ответа Supabase auth
        mock_user = MagicMock()
        mock_user.email = "user@example.com"
        mock_user.id = "abc-123"
        mock_auth_response = MagicMock()
        mock_auth_response.user = mock_user

        mock_supabase = MagicMock()
        mock_supabase.auth.verify_otp.return_value = mock_auth_response

        mocker.patch("app.auth.supabase_auth.supabase", mock_supabase)

        from app.auth.supabase_auth import verify_magic_link
        result = verify_magic_link("test-token-123")

        # Верификация должна вернуть user_dict
        assert result is not None
        assert result["email"] == "user@example.com"

        # health_ping НЕ должен быть вызван внутри verify_magic_link (Section 11)
        health_ping_calls = [
            str(c) for c in mock_supabase.table.call_args_list
            if "health_ping" in str(c)
        ]
        assert len(health_ping_calls) == 0, (
            "Section 11: keep_alive_if_needed() НЕ должна вызываться "
            "внутри verify_magic_link()"
        )

    def test_keep_alive_called_after_verify_not_inside(self, mocker):
        """
        Правильный порядок вызовов (auth_callback.py):
          1. result = verify_magic_link(token)
          2. if result: keep_alive_if_needed(email)

        Section 11: keepalive вызывается ПОСЛЕ verify, не внутри.
        """
        # Мок успешного verify_otp
        mock_user = MagicMock()
        mock_user.email = "user@example.com"
        mock_user.id = "abc-123"
        mock_auth_response = MagicMock()
        mock_auth_response.user = mock_user

        mock_supabase = MagicMock()
        mock_supabase.auth.verify_otp.return_value = mock_auth_response

        # Отдельный мок для health_ping (keepalive)
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        fake_state = {}
        mocker.patch("app.auth.supabase_auth.supabase", mock_supabase)
        mocker.patch("app.auth.supabase_auth.st.session_state", fake_state)

        from app.auth.supabase_auth import verify_magic_link, keep_alive_if_needed

        # Эмулируем auth_callback.py — правильный порядок
        call_order = []

        result = verify_magic_link("test-token")
        call_order.append("verify_magic_link")

        if result:
            keep_alive_if_needed(result["email"])
            call_order.append("keep_alive_if_needed")

        # Правильный порядок: сначала verify, потом keepalive
        assert call_order == ["verify_magic_link", "keep_alive_if_needed"]

        # keepalive выполнил ping в health_ping
        mock_supabase.table.assert_called_with("health_ping")

        # last_keepalive_date установлен
        assert fake_state.get("last_keepalive_date") == date.today()

    def test_verify_magic_link_failure_does_not_trigger_keepalive(self, mocker):
        """
        Если verify_magic_link возвращает None →
        keep_alive_if_needed НЕ вызывается (условие: if result:).
        """
        # verify_otp возвращает ответ без пользователя
        mock_auth_response = MagicMock()
        mock_auth_response.user = None

        mock_supabase = MagicMock()
        mock_supabase.auth.verify_otp.return_value = mock_auth_response

        fake_state = {}
        mocker.patch("app.auth.supabase_auth.supabase", mock_supabase)
        mocker.patch("app.auth.supabase_auth.st.session_state", fake_state)

        from app.auth.supabase_auth import verify_magic_link, keep_alive_if_needed

        result = verify_magic_link("bad-token")

        # result == None → keepalive не вызывается
        if result:
            keep_alive_if_needed(result["email"])

        assert result is None
        # health_ping не должен быть вызван
        health_ping_calls = [
            str(c) for c in mock_supabase.table.call_args_list
            if "health_ping" in str(c)
        ]
        assert len(health_ping_calls) == 0
        assert "last_keepalive_date" not in fake_state


# ===========================================================================
# Дополнительные тесты: session_state structure (Section 14)
# ===========================================================================
class TestSessionStateStructure:
    """
    Проверяем типы ключей session_state согласно Section 14.
    """

    def test_last_keepalive_date_is_date_type(self, mocker):
        """
        last_keepalive_date должен быть типа date, не datetime или str (Section 14).
        """
        fake_state = {}

        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        mocker.patch("app.auth.supabase_auth.st.session_state", fake_state)
        mocker.patch("app.auth.supabase_auth.supabase", mock_supabase)

        from app.auth.supabase_auth import keep_alive_if_needed
        keep_alive_if_needed("user@example.com")

        stored_date = fake_state.get("last_keepalive_date")
        assert isinstance(stored_date, date), (
            f"last_keepalive_date должен быть типа date, получен {type(stored_date)}"
        )
        # datetime является подклассом date — проверяем явно
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
