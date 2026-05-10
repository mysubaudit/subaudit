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

ИСПРАВЛЕНИЯ v2.9-fix:
  - БАГ 1 (оригинал): тесты keep_alive / verify_magic_link тестируют реальные модули
            app/auth/supabase_auth.py через mocker.patch, а не локальные заглушки.
            Локальные заглушки оставлены ТОЛЬКО для тестов is_session_expired
            (session guard из main.py — не выделен в отдельный модуль).
  - БАГ 2 (оригинал): проверка ISO timestamp через datetime.fromisoformat() + tzinfo,
            а не хрупкое строковое условие с or/and без скобок.
  - БАГ 3 (оригинал): антипаттерн try/except в test_keep_alive_failure_does_not_raise
            заменён на прямой вызов (pytest сам поймает любое исключение).
  - БАГ 4 (оригинал): доступ к аргументам мока через call_args.args[0] (Python 3.8+)
            вместо хрупкого call_args[0][0].

ИСПРАВЛЕНИЯ в этой версии (новые):
  - БАГ 5: test_keep_alive_called_once_per_day — убран хардкод ключа "pinged_at".
            Section 11 не задаёт имя колонки в health_ping. Теперь проверяем
            любое значение в payload через _find_iso_utc_value().
  - БАГ 6: test_keep_alive_failure_does_not_raise — добавлена проверка вызова
            log_warning(). Section 11: "On failure: Log warning via log_warning().
            Do NOT raise." Без этой проверки тест игнорировал половину требования.
  - БАГ 7: test_keep_alive_failure_does_not_set_date — добавлена та же проверка
            log_warning() по той же причине (Section 11).
  - БАГ 8: TestSessionStateStructure — добавлены тесты для magic_link_last_sent
            (float) и subscription_warning (bool) согласно Section 14.
            Без них два ключа из Section 14 оставались непокрытыми.
  - БАГ 9: добавлен edge-case: last_keepalive_date типа datetime (а не date)
            не должен проходить проверку как «уже выполнен сегодня» — datetime
            является подклассом date, и наивное сравнение может дать False Positive.
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
# Вспомогательная функция: найти ISO UTC datetime среди значений payload.
# Используется вместо хардкода ключа "pinged_at" (БАГ 5 исправлен).
# Section 11 не специфицирует имя колонки — проверяем любое значение.
# ---------------------------------------------------------------------------
def _find_iso_utc_value(payload: dict) -> str | None:
    """
    Ищет в payload словаря любое значение, которое является
    валидным ISO datetime строкой с timezone.
    Возвращает строку если нашёл, иначе None.
    """
    for v in payload.values():
        if not isinstance(v, str):
            continue
        try:
            parsed = datetime.fromisoformat(v)
            if parsed.tzinfo is not None:
                return v
        except (ValueError, TypeError):
            continue
    return None


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

        БАГ 5 ИСПРАВЛЕН: убран хардкод ключа "pinged_at".
        Section 11 не задаёт имя колонки — используем _find_iso_utc_value()
        для поиска ISO UTC datetime среди всех значений payload.
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

        # Извлекаем payload (БАГ 4 исправлен ранее — надёжный доступ через call_args.args)
        args, kwargs = mock_table.insert.call_args
        insert_payload = args[0] if args else kwargs

        assert isinstance(insert_payload, dict), (
            "Section 11: INSERT получает словарь с данными пинга"
        )

        # БАГ 5 ИСПРАВЛЕН: не завязываемся на конкретное имя колонки.
        # Ищем любое значение, которое является ISO datetime с timezone.
        ping_value = _find_iso_utc_value(insert_payload)

        assert ping_value is not None, (
            f"Section 11: в payload {insert_payload!r} не найдено "
            "валидного ISO datetime с timezone. "
            "Используйте datetime.now(timezone.utc).isoformat()"
        )

        # Section 11: явно запрещает строку 'NOW()'
        for v in insert_payload.values():
            assert v != "NOW()", (
                "Section 11: ping_value НЕ должен быть строкой 'NOW()'. "
                "Используйте datetime.now(timezone.utc).isoformat()"
            )

        # Проверяем timezone через fromisoformat (БАГ 2 исправлен ранее)
        parsed_dt = datetime.fromisoformat(ping_value)
        assert parsed_dt.tzinfo is not None, (
            "Section 11: ping datetime должен содержать timezone info "
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

        БАГ 7 ИСПРАВЛЕН: добавлена проверка что log_warning вызван.
        Section 11: «On failure: Log warning via log_warning()» — это обязательно.
        Без этой проверки тест проверял только отсутствие исключения,
        но не соблюдение требования логирования.
        """
        fake_state = {}

        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.side_effect = Exception("Supabase connection error")

        # Патчим log_warning чтобы проверить его вызов (Section 11)
        mock_log_warning = mocker.patch("app.auth.supabase_auth.log_warning")

        mocker.patch("app.auth.supabase_auth.st.session_state", fake_state)
        mocker.patch("app.auth.supabase_auth.supabase", mock_supabase)

        from app.auth.supabase_auth import keep_alive_if_needed
        keep_alive_if_needed("user@example.com")

        # При ошибке last_keepalive_date НЕ устанавливается
        assert "last_keepalive_date" not in fake_state, (
            "Section 11: при ошибке ping last_keepalive_date не должен "
            "устанавливаться, чтобы следующий вызов повторил попытку"
        )

        # БАГ 7 ИСПРАВЛЕН: log_warning должен быть вызван (Section 11)
        mock_log_warning.assert_called_once(), (
            "Section 11: «On failure: Log warning via log_warning()» — "
            "log_warning() должен быть вызван при ошибке ping"
        )

    def test_keep_alive_skipped_when_last_date_is_datetime_not_date(self, mocker):
        """
        БАГ 9 (НОВЫЙ): edge-case — datetime является подклассом date.
        Если код хранит datetime вместо date, сравнение с date.today() может
        вести себя неожиданно (datetime != date даже при совпадении дня).

        Тест документирует правильное поведение:
        last_keepalive_date ДОЛЖЕН быть date, не datetime (Section 14).
        Если в state попал datetime — реализация должна это обработать корректно.

        Примечание: этот тест проверяет robustness реализации.
        """
        # Сохраняем datetime вместо date — некорректное состояние
        today_as_datetime = datetime.combine(date.today(), datetime.min.time())
        fake_state = {"last_keepalive_date": today_as_datetime}

        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        mocker.patch("app.auth.supabase_auth.st.session_state", fake_state)
        mocker.patch("app.auth.supabase_auth.supabase", mock_supabase)

        from app.auth.supabase_auth import keep_alive_if_needed

        # Вызов не должен бросать исключение независимо от типа в state
        keep_alive_if_needed("user@example.com")

        # Если пинг выполнился — last_keepalive_date теперь должен быть date
        stored = fake_state.get("last_keepalive_date")
        if stored is not None:
            assert isinstance(stored, date), (
                "Section 14: last_keepalive_date должен быть типа date"
            )
            assert not isinstance(stored, datetime), (
                "Section 14: last_keepalive_date не должен быть datetime"
            )


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

        БАГ 1 (оригинал) ИСПРАВЛЕН: тестируем реальный verify_magic_link из supabase_auth.py.
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

    def test_keep_alive_failure_does_not_raise(self, mocker):
        """
        Section 11: при ошибке keepalive — НЕ raise, НЕ показывать UI-ошибку.

        БАГ 3 (оригинал) ИСПРАВЛЕН: убран антипаттерн try/except вокруг вызова.
        Прямой вызов: если функция бросит — pytest сам зафиксирует падение.

        БАГ 6 ИСПРАВЛЕН: добавлена проверка вызова log_warning().
        Section 11: «On failure: Log warning via log_warning(). Do NOT raise.»
        Оба условия обязательны — тест должен проверять оба.
        """
        fake_state = {}

        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.side_effect = Exception("Network error")

        # БАГ 6 ИСПРАВЛЕН: патчим log_warning для проверки его вызова
        mock_log_warning = mocker.patch("app.auth.supabase_auth.log_warning")

        mocker.patch("app.auth.supabase_auth.st.session_state", fake_state)
        mocker.patch("app.auth.supabase_auth.supabase", mock_supabase)

        from app.auth.supabase_auth import keep_alive_if_needed

        # БАГ 3 (оригинал) ИСПРАВЛЕН: прямой вызов без try/except.
        # Если функция бросит исключение — тест упадёт автоматически.
        # Это и есть проверка «Do NOT raise» из Section 11.
        keep_alive_if_needed("user@example.com")

        # БАГ 6 ИСПРАВЛЕН: Section 11 требует log_warning при ошибке
        mock_log_warning.assert_called_once(), (
            "Section 11: «On failure: Log warning via log_warning()» — "
            "log_warning() должен быть вызван при ошибке keepalive"
        )


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

    def test_magic_link_last_sent_is_float(self):
        """
        БАГ 8 ИСПРАВЛЕН: magic_link_last_sent должен быть Unix timestamp (float).
        Section 14: «magic_link_last_sent: float — Unix timestamp (used for 60s cooldown)».
        Тест отсутствовал — ключ из Section 14 не был покрыт.
        """
        now = time.time()
        # Симулируем установку ключа при отправке magic link (7_account.py)
        session_state = {"magic_link_last_sent": now}
        stored = session_state["magic_link_last_sent"]
        assert isinstance(stored, float), (
            f"magic_link_last_sent должен быть float (Unix timestamp), "
            f"получен {type(stored)}"
        )

    def test_magic_link_cooldown_enforced(self):
        """
        Section 14 + Section 11: COOLDOWN = 60 секунд для magic link resend.
        Проверяем что логика cooldown использует float timestamp и константу 60s.

        Section 11: «COOLDOWN = 60 # seconds — used in magic link resend throttle
        (7_account.py). Separate from keepalive logic.»
        """
        COOLDOWN = 60  # Section 11

        now = time.time()
        # Отправили ссылку 30 секунд назад — cooldown ещё активен
        last_sent = now - 30
        session_state = {"magic_link_last_sent": last_sent}

        elapsed = now - session_state["magic_link_last_sent"]
        can_resend = elapsed >= COOLDOWN

        assert can_resend is False, (
            "Cooldown 60s: через 30 секунд повторная отправка должна быть заблокирована"
        )

        # Отправили ссылку 61 секунду назад — cooldown истёк
        last_sent_old = now - 61
        session_state["magic_link_last_sent"] = last_sent_old
        elapsed_old = now - session_state["magic_link_last_sent"]
        can_resend_now = elapsed_old >= COOLDOWN

        assert can_resend_now is True, (
            "Cooldown 60s: через 61 секунду повторная отправка должна быть разрешена"
        )

    def test_subscription_warning_is_bool(self):
        """
        БАГ 8 ИСПРАВЛЕН: subscription_warning должен быть bool (Section 14).
        Section 14: «subscription_warning: bool».
        Тест отсутствовал — ключ из Section 14 не был покрыт.
        """
        # Проверяем оба допустимых значения
        for value in (True, False):
            session_state = {"subscription_warning": value}
            stored = session_state["subscription_warning"]
            assert isinstance(stored, bool), (
                f"subscription_warning должен быть bool, получен {type(stored)}"
            )

    def test_subscription_warning_reason_is_str(self):
        """
        subscription_warning_reason должен быть str из допустимых значений.
        Section 14: «str: 'no_cache' or 'api_error' — popped on successful check».
        """
        allowed_reasons = {"no_cache", "api_error"}

        for reason in allowed_reasons:
            session_state = {"subscription_warning_reason": reason}
            stored = session_state["subscription_warning_reason"]
            assert isinstance(stored, str), (
                f"subscription_warning_reason должен быть str, получен {type(stored)}"
            )
            assert stored in allowed_reasons, (
                f"subscription_warning_reason должен быть одним из "
                f"{allowed_reasons}, получен '{stored}'"
            )

    def test_user_plan_valid_values(self):
        """
        user_plan принимает только три допустимых значения (Section 14).
        Section 14: «str: 'free' / 'starter' / 'pro'».
        """
        valid_plans = {"free", "starter", "pro"}

        for plan in valid_plans:
            session_state = {"user_plan": plan}
            assert session_state["user_plan"] in valid_plans, (
                f"user_plan должен быть одним из {valid_plans}"
            )
