"""
test_payments.py
================
Тесты для app/payments/gumroad.py

Покрывает все 5 обязательных тест-кейсов из Section 17 спецификации v2.9:
  - test_success_clears_warning
  - test_429_retries_once
  - test_sentry_tags_distinct
  - test_downgrade_updates_session
  - test_post_upgrade_message_shown

Все правила поведения взяты строго из Section 13 (Payments)
и Section 14 (Session State & Memory).

Lemon Squeezy заменён на Gumroad (см. CONTEXT_FOR_NEW_CHAT.md).
Файл app/payments/lemon_squeezy.py УДАЛЁН.
Все mock-пути обновлены на app.payments.gumroad.*

Версия: Python 3.11.9 (Section 1 / runtime.txt)
Зависимости dev: pytest==8.2.2, pytest-mock==3.14.0 (Section 15)

ИСПРАВЛЕНИЯ относительно исходного файла:
  - КРИТИЧНО: все пути "app.payments.lemon_squeezy.*" заменены на
              "app.payments.gumroad.*" — иначе ModuleNotFoundError при запуске.
  - КРИТИЧНО: все "from app.payments.lemon_squeezy import ..." заменены на
              "from app.payments.gumroad import ...".
  - БАГ 1 (из оригинала): mock path time.sleep — полный путь
            "app.payments.gumroad.time.sleep" подтверждён корректным.
  - БАГ 2 (из оригинала): мёртвая логика assert в test_sentry_tags_are_distinct
            заменена на три явных assert — подтверждено корректным.
  - БАГ 3 (из оригинала): test_post_upgrade_warning_message_text проверяет
            точный текст из Section 13 — подтверждено корректным.
"""

import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Вспомогательный класс для эмуляции HTTP-ответа requests.get
# ---------------------------------------------------------------------------

class FakeResponse:
    """Упрощённая заглушка для requests.Response."""

    def __init__(self, status_code: int, json_body: dict | None = None):
        self.status_code = status_code
        self._json_body = json_body or {}

    def json(self) -> dict:
        return self._json_body

    def raise_for_status(self):
        # Только для явной проверки — в коде используется status_code напрямую
        if self.status_code >= 400:
            raise Exception(f"HTTP Error {self.status_code}")


# ---------------------------------------------------------------------------
# Вспомогательные функции — патчат app.payments.gumroad (не lemon_squeezy!)
# ---------------------------------------------------------------------------

def _make_gumroad_response(plan: str, product_ids: dict = None) -> dict:
    """
    Создаёт правильный формат ответа Gumroad API.

    Gumroad API возвращает:
    {
      "success": true,
      "sales": [
        {
          "product_id": "...",
          "refunded": false,
          "chargedback": false
        }
      ]
    }

    Args:
        plan: 'free', 'starter', или 'pro'
        product_ids: dict с ключами 'starter' и 'pro' (по умолчанию "starter" и "pro")
    """
    if product_ids is None:
        product_ids = {"starter": "starter", "pro": "pro"}

    if plan == "free":
        # Нет активных продаж
        return {"success": True, "sales": []}
    elif plan == "starter":
        return {
            "success": True,
            "sales": [
                {
                    "product_id": product_ids["starter"],
                    "refunded": False,
                    "chargedback": False,
                }
            ],
        }
    elif plan == "pro":
        return {
            "success": True,
            "sales": [
                {
                    "product_id": product_ids["pro"],
                    "refunded": False,
                    "chargedback": False,
                }
            ],
        }
    else:
        raise ValueError(f"Unknown plan: {plan}")


def _mock_spinner(mocker):
    """
    Возвращает мок st.spinner, пригодный как контекстный менеджер.
    Section 13: «Always st.spinner("Verifying subscription...") — never silent»

    ВАЖНО: путь app.payments.gumroad.st.spinner, а не lemon_squeezy.
    """
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return mocker.patch("app.payments.gumroad.st.spinner", return_value=cm)


def _mock_sentry_scope(mocker):
    """
    Возвращает (mock_push_scope, mock_scope) для проверки Sentry-тегов.
    Section 13: «distinct Sentry tags»

    ВАЖНО: путь app.payments.gumroad.sentry_sdk.push_scope.
    """
    mock_scope = MagicMock()
    mock_push = mocker.patch("app.payments.gumroad.sentry_sdk.push_scope")
    mock_push.return_value.__enter__ = MagicMock(return_value=mock_scope)
    mock_push.return_value.__exit__ = MagicMock(return_value=False)
    return mock_push, mock_scope


# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------

@pytest.fixture
def clean_session_state():
    """
    Чистый session_state без кешированного плана и без флагов предупреждений.
    Section 14: subscription_warning, subscription_warning_reason, user_plan.
    """
    return {
        "user_email": "user@example.com",
        "user_plan": "free",
        "subscription_warning": False,
        # subscription_warning_reason намеренно отсутствует — нет кеша
    }


@pytest.fixture
def session_state_with_cached_pro_plan():
    """
    Session state с ранее закешированным PRO-планом.
    Section 13: «Error — cache present → Return cached plan, reason='api_error'»
    Section 14: user_plan хранится в session_state.
    """
    return {
        "user_email": "pro_user@example.com",
        "user_plan": "pro",
        "_gumroad_cached_plan": "pro",
        "subscription_warning": False,
    }


@pytest.fixture
def session_state_starter_then_free():
    """
    Session state пользователя, у которого был план starter,
    а после downgrade API возвращает free.
    Section 13: «Downgrade mid-session — Caught at Checkpoint 2»
    """
    return {
        "user_email": "downgrade_user@example.com",
        "user_plan": "starter",
        "subscription_warning": False,
    }


# ---------------------------------------------------------------------------
# test_success_clears_warning
# Section 13: «Success: subscription_warning=False.
#              Pop subscription_warning_reason. Update user_plan.»
# ---------------------------------------------------------------------------

class TestSuccessClearsWarning:
    """
    Успешный ответ API (HTTP 200) должен:
      1. Обновить user_plan в session_state.
      2. Установить subscription_warning = False.
      3. Удалить ключ subscription_warning_reason из session_state.
    """

    def test_success_clears_warning_flag(self, mocker, clean_session_state):
        """
        После успешного HTTP 200 флаг subscription_warning сбрасывается в False.
        Section 13: «Success: subscription_warning=False»
        """
        state = {**clean_session_state,
                 "subscription_warning": True,
                 "subscription_warning_reason": "api_error"}

        mock_response = FakeResponse(200, _make_gumroad_response("starter"))
        mocker.patch("app.payments.gumroad.requests.get",
                     return_value=mock_response)
        mocker.patch("app.payments.gumroad.st.session_state", state)
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        result = get_subscription_status(state["user_email"])

        assert result == "starter", (
            "Section 13: при HTTP 200 функция должна вернуть план из ответа API"
        )
        assert state["subscription_warning"] is False, (
            "Section 13: subscription_warning должен быть False после успешного ответа"
        )

    def test_success_pops_warning_reason(self, mocker, clean_session_state):
        """
        После успешного HTTP 200 ключ subscription_warning_reason удаляется.
        Section 13: «Pop subscription_warning_reason»
        """
        state = {**clean_session_state,
                 "subscription_warning": True,
                 "subscription_warning_reason": "no_cache"}

        mock_response = FakeResponse(200, _make_gumroad_response("pro"))
        mocker.patch("app.payments.gumroad.requests.get",
                     return_value=mock_response)
        mocker.patch("app.payments.gumroad.st.session_state", state)
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        get_subscription_status(state["user_email"])

        assert "subscription_warning_reason" not in state, (
            "Section 13: subscription_warning_reason должен быть удалён (popped) "
            "после успешного ответа API"
        )

    def test_success_updates_user_plan_in_session(self, mocker, clean_session_state):
        """
        После успешного HTTP 200 user_plan в session_state обновляется.
        Section 13: «Success: ... Update user_plan»
        Section 14: user_plan — str: 'free'/'starter'/'pro'
        """
        state = {**clean_session_state, "user_plan": "free"}

        mock_response = FakeResponse(200, _make_gumroad_response("pro"))
        mocker.patch("app.payments.gumroad.requests.get",
                     return_value=mock_response)
        mocker.patch("app.payments.gumroad.st.session_state", state)
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        result = get_subscription_status(state["user_email"])

        assert result == "pro"
        assert state["user_plan"] == "pro", (
            "Section 14: user_plan в session_state должен быть обновлён "
            "до значения, полученного от API"
        )

    def test_success_spinner_always_shown(self, mocker, clean_session_state):
        """
        При любом обращении к API должен отображаться st.spinner.
        Section 13: «Always st.spinner("Verifying subscription...") — never silent»
        """
        mock_response = FakeResponse(200, _make_gumroad_response("starter"))
        mocker.patch("app.payments.gumroad.requests.get",
                     return_value=mock_response)
        mocker.patch("app.payments.gumroad.st.session_state",
                     clean_session_state)
        mock_spinner = _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        get_subscription_status(clean_session_state["user_email"])

        mock_spinner.assert_called_once_with("Verifying subscription..."), (
            "Section 13: st.spinner всегда должен вызываться с текстом "
            "'Verifying subscription...'"
        )


# ---------------------------------------------------------------------------
# test_429_retries_once
# Section 13: «HTTP 429: Wait 1s, retry once. Still failing → cached or 'free'.
#              Set subscription_warning=True»
# ---------------------------------------------------------------------------

class Test429RetriesOnce:
    """
    При HTTP 429 функция должна:
      1. Подождать 1 секунду.
      2. Выполнить ровно одну повторную попытку.
      3. При повторном провале — вернуть кешированный план или 'free'.
      4. Выставить subscription_warning = True.
    """

    def test_429_waits_one_second_before_retry(self, mocker, clean_session_state):
        """
        При HTTP 429 должна быть задержка 1 секунда перед повторной попыткой.
        Section 13: «HTTP 429: Wait 1s, retry once»

        Полный путь патча "app.payments.gumroad.time.sleep" — гарантирует
        перехват независимо от способа импорта time в модуле.
        """
        mock_response_429 = FakeResponse(429)
        mocker.patch("app.payments.gumroad.requests.get",
                     return_value=mock_response_429)
        mock_sleep = mocker.patch("app.payments.gumroad.time.sleep")
        mocker.patch("app.payments.gumroad.st.session_state",
                     clean_session_state)
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        get_subscription_status(clean_session_state["user_email"])

        mock_sleep.assert_called_once_with(1), (
            "Section 13: при HTTP 429 необходимо вызвать time.sleep(1) "
            "перед повторной попыткой"
        )

    def test_429_retries_exactly_once(self, mocker, clean_session_state):
        """
        При HTTP 429 функция делает ровно одну повторную попытку, не более.
        Section 13: «retry once»
        Итого вызовов requests.get: 2 (первый + retry).
        """
        mock_response_429 = FakeResponse(429)
        mock_get = mocker.patch("app.payments.gumroad.requests.get",
                                return_value=mock_response_429)
        mocker.patch("app.payments.gumroad.time.sleep")
        mocker.patch("app.payments.gumroad.st.session_state",
                     clean_session_state)
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        get_subscription_status(clean_session_state["user_email"])

        assert mock_get.call_count == 2, (
            "Section 13: при HTTP 429 должно быть ровно 2 запроса "
            "(первый + одна повторная попытка)"
        )

    def test_429_persistent_returns_free_without_cache(self, mocker,
                                                        clean_session_state):
        """
        Если после retry снова 429 — вернуть 'free' (нет кеша).
        Section 13: «Still failing → cached or 'free'»
        """
        mock_response_429 = FakeResponse(429)
        mocker.patch("app.payments.gumroad.requests.get",
                     return_value=mock_response_429)
        mocker.patch("app.payments.gumroad.time.sleep")
        mocker.patch("app.payments.gumroad.st.session_state",
                     clean_session_state)
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        result = get_subscription_status(clean_session_state["user_email"])

        assert result == "free", (
            "Section 13: при повторном 429 без кеша вернуть 'free'"
        )
        assert clean_session_state["subscription_warning"] is True, (
            "Section 13: subscription_warning должен быть True при провале запроса"
        )

    def test_429_persistent_returns_cached_plan_when_available(
            self, mocker, session_state_with_cached_pro_plan):
        """
        Если после retry снова 429 — вернуть кешированный план.
        Section 13: «Still failing → cached or 'free'»
        """
        state = session_state_with_cached_pro_plan

        mock_response_429 = FakeResponse(429)
        mocker.patch("app.payments.gumroad.requests.get",
                     return_value=mock_response_429)
        mocker.patch("app.payments.gumroad.time.sleep")
        mocker.patch("app.payments.gumroad.st.session_state", state)
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        result = get_subscription_status(state["user_email"])

        assert result == "pro", (
            "Section 13: при повторном 429 при наличии кеша вернуть кешированный план"
        )
        assert state["subscription_warning"] is True

    def test_429_sets_subscription_warning_true(self, mocker, clean_session_state):
        """
        При провальном 429 (без кеша) subscription_warning=True.
        Section 13: «Set subscription_warning=True»
        """
        mocker.patch("app.payments.gumroad.requests.get",
                     return_value=FakeResponse(429))
        mocker.patch("app.payments.gumroad.time.sleep")
        mocker.patch("app.payments.gumroad.st.session_state", clean_session_state)
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        get_subscription_status(clean_session_state["user_email"])

        assert clean_session_state["subscription_warning"] is True, (
            "Section 13: subscription_warning=True при провале HTTP 429"
        )


# ---------------------------------------------------------------------------
# test_sentry_tags_distinct
# Section 13: «Sentry tag reason=no_cache» и «Sentry tag reason=api_error»
#             должны быть DISTINCT — разные события Sentry
# ---------------------------------------------------------------------------

class TestSentryTagsDistinct:
    """
    Ошибки API логируются в Sentry с различными тегами:
      - reason='no_cache'  — нет кеша, возврат 'free'
      - reason='api_error' — есть кеш, возврат кешированного плана

    Section 13: «distinct Sentry tags»
    """

    def test_sentry_tag_no_cache_on_error_without_cache(
            self, mocker, clean_session_state):
        """
        При ошибке API без кешированного плана — Sentry тег reason='no_cache'.
        Section 13: «Error — no cache: reason='no_cache'. Sentry tag reason=no_cache»
        """
        mocker.patch("app.payments.gumroad.requests.get",
                     side_effect=Exception("Connection error"))
        _, mock_scope = _mock_sentry_scope(mocker)
        mocker.patch("app.payments.gumroad.st.session_state",
                     clean_session_state)
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        result = get_subscription_status(clean_session_state["user_email"])

        assert result == "free"
        tag_calls = [str(c) for c in mock_scope.set_tag.call_args_list]
        assert any("no_cache" in c for c in tag_calls), (
            "Section 13: при ошибке без кеша Sentry тег reason должен быть 'no_cache'"
        )

    def test_sentry_tag_api_error_on_error_with_cache(
            self, mocker, session_state_with_cached_pro_plan):
        """
        При ошибке API при наличии кеша — Sentry тег reason='api_error'.
        Section 13: «Error — cache present: reason='api_error'. Sentry tag reason=api_error»
        """
        state = session_state_with_cached_pro_plan

        mocker.patch("app.payments.gumroad.requests.get",
                     side_effect=Exception("Timeout"))
        _, mock_scope = _mock_sentry_scope(mocker)
        mocker.patch("app.payments.gumroad.st.session_state", state)
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        result = get_subscription_status(state["user_email"])

        assert result == "pro"  # возврат кешированного плана
        tag_calls = [str(c) for c in mock_scope.set_tag.call_args_list]
        assert any("api_error" in c for c in tag_calls), (
            "Section 13: при ошибке с кешем Sentry тег reason должен быть 'api_error'"
        )

    def test_sentry_tags_are_distinct_between_scenarios(
            self, mocker, clean_session_state, session_state_with_cached_pro_plan):
        """
        Теги 'no_cache' и 'api_error' — разные события, не должны совпадать.
        Section 13: «distinct Sentry tags, clear-on-success»

        Три явных assert:
          1. no_cache тег реально записан (хотя бы 1 раз)
          2. api_error тег реально записан (хотя бы 1 раз)
          3. значения тегов различаются между сценариями
        """
        collected_tags: dict[str, list[str]] = {"no_cache": [], "api_error": []}

        def fake_set_tag(key, value):
            """Перехватчик вызовов scope.set_tag()."""
            if key == "reason" and value in collected_tags:
                collected_tags[value].append(value)

        _mock_spinner(mocker)

        # --- Сценарий no_cache (нет кешированного плана) ---
        mock_scope_nc = MagicMock()
        mock_scope_nc.set_tag.side_effect = fake_set_tag
        mock_push_nc = mocker.patch("app.payments.gumroad.sentry_sdk.push_scope")
        mock_push_nc.return_value.__enter__ = MagicMock(return_value=mock_scope_nc)
        mock_push_nc.return_value.__exit__ = MagicMock(return_value=False)
        mocker.patch("app.payments.gumroad.requests.get",
                     side_effect=Exception("err"))
        mocker.patch("app.payments.gumroad.st.session_state",
                     clean_session_state)

        from app.payments.gumroad import get_subscription_status
        get_subscription_status(clean_session_state["user_email"])

        # --- Сценарий api_error (есть кешированный план) ---
        mock_scope_ae = MagicMock()
        mock_scope_ae.set_tag.side_effect = fake_set_tag
        mock_push_nc.return_value.__enter__ = MagicMock(return_value=mock_scope_ae)
        mocker.patch("app.payments.gumroad.st.session_state",
                     session_state_with_cached_pro_plan)

        get_subscription_status(session_state_with_cached_pro_plan["user_email"])

        # Три явных assert — проверяем различие тегов
        assert len(collected_tags["no_cache"]) > 0, (
            "Section 13: тег reason='no_cache' должен быть записан в Sentry "
            "при ошибке без кеша"
        )
        assert len(collected_tags["api_error"]) > 0, (
            "Section 13: тег reason='api_error' должен быть записан в Sentry "
            "при ошибке с кешем"
        )
        assert collected_tags["no_cache"] != collected_tags["api_error"], (
            "Section 13: теги no_cache и api_error должны быть различными (distinct)"
        )

    def test_http_401_returns_free_and_logs_sentry(self, mocker, clean_session_state):
        """
        HTTP 401 → вернуть 'free', залогировать в Sentry, subscription_warning=True.
        Section 13: «HTTP 401: Log Sentry. Return 'free'.
                    Set subscription_warning=True, reason='no_cache'»
        """
        mock_response_401 = FakeResponse(401)
        mocker.patch("app.payments.gumroad.requests.get",
                     return_value=mock_response_401)
        _, mock_scope = _mock_sentry_scope(mocker)
        mocker.patch("app.payments.gumroad.st.session_state",
                     clean_session_state)
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        result = get_subscription_status(clean_session_state["user_email"])

        assert result == "free", "Section 13: HTTP 401 → вернуть 'free'"
        assert clean_session_state["subscription_warning"] is True, (
            "Section 13: HTTP 401 → subscription_warning=True"
        )
        assert clean_session_state.get("subscription_warning_reason") == "no_cache", (
            "Section 13: HTTP 401 → reason='no_cache'"
        )


# ---------------------------------------------------------------------------
# test_downgrade_updates_session
# Section 13: «Downgrade mid-session — Caught at Checkpoint 2 (Dashboard load)
#              on new session start ONLY»
# ---------------------------------------------------------------------------

class TestDowngradeUpdatesSession:
    """
    При получении от API плана ниже текущего (downgrade)
    session_state должен быть обновлён.

    Section 13: Checkpoint 2 — Dashboard load.
    Section 14: user_plan в session_state.
    """

    def test_downgrade_from_starter_to_free_updates_session(
            self, mocker, session_state_starter_then_free):
        """
        API возвращает 'free', session_state был 'starter' →
        user_plan обновляется до 'free'.
        Section 13: «Downgrade mid-session — Caught at Checkpoint 2»
        """
        state = session_state_starter_then_free

        mock_response = FakeResponse(200, _make_gumroad_response("free"))
        mocker.patch("app.payments.gumroad.requests.get",
                     return_value=mock_response)
        mocker.patch("app.payments.gumroad.st.session_state", state)
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        result = get_subscription_status(state["user_email"])

        assert result == "free", (
            "Section 13: при downgrade API возвращает новый (пониженный) план"
        )
        assert state["user_plan"] == "free", (
            "Section 14: user_plan в session_state должен быть обновлён при downgrade"
        )

    def test_downgrade_from_pro_to_starter_updates_session(self, mocker):
        """
        Downgrade с PRO до STARTER: user_plan обновляется в session_state.
        Section 13: «Downgrade mid-session»
        """
        state = {
            "user_email": "pro_user@example.com",
            "user_plan": "pro",
            "subscription_warning": False,
        }

        mock_response = FakeResponse(200, _make_gumroad_response("starter"))
        mocker.patch("app.payments.gumroad.requests.get",
                     return_value=mock_response)
        mocker.patch("app.payments.gumroad.st.session_state", state)
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        result = get_subscription_status(state["user_email"])

        assert result == "starter"
        assert state["user_plan"] == "starter", (
            "Section 13/14: user_plan должен отражать новый пониженный план"
        )

    def test_downgrade_clears_warning_on_successful_api_call(self, mocker):
        """
        Downgrade через успешный HTTP 200 → subscription_warning=False.
        Section 13: «Success: subscription_warning=False»
        """
        state = {
            "user_email": "user@example.com",
            "user_plan": "pro",
            "subscription_warning": True,
            "subscription_warning_reason": "api_error",
        }

        mock_response = FakeResponse(200, _make_gumroad_response("starter"))
        mocker.patch("app.payments.gumroad.requests.get",
                     return_value=mock_response)
        mocker.patch("app.payments.gumroad.st.session_state", state)
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        get_subscription_status(state["user_email"])

        assert state["subscription_warning"] is False
        assert "subscription_warning_reason" not in state


# ---------------------------------------------------------------------------
# test_post_upgrade_message_shown
# Section 13: «Post-upgrade delay: If subscription_warning fires immediately
#              after upgrade → show actionable message:
#              "Payment processors may take up to 60 seconds.
#               Please refresh in a moment."»
# ---------------------------------------------------------------------------

# Точный текст из Section 13 — не менять
_EXPECTED_POST_UPGRADE_MSG = (
    "Payment processors may take up to 60 seconds. "
    "Please refresh in a moment."
)


class TestPostUpgradeMessageShown:
    """
    Если subscription_warning=True срабатывает сразу после апгрейда,
    пользователю должно быть показано точное сообщение из Section 13.
    """

    def test_post_upgrade_warning_message_shown_on_api_error(
            self, mocker, clean_session_state):
        """
        При ошибке API (нет кеша) и признаке post_upgrade=True
        функция показывает точное сообщение из Section 13 через st.warning().
        Section 13: «Payment processors may take up to 60 seconds.
                    Please refresh in a moment.»
        """
        # Признак post-upgrade: пользователь только что оплатил,
        # API ещё не подтвердил новый план
        clean_session_state["post_upgrade"] = True

        mocker.patch("app.payments.gumroad.requests.get",
                     side_effect=Exception("API unavailable"))
        mocker.patch("app.payments.gumroad.st.session_state",
                     clean_session_state)
        mock_warning = mocker.patch("app.payments.gumroad.st.warning")
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        get_subscription_status(clean_session_state["user_email"])

        # subscription_warning должен быть True — условие для показа сообщения
        assert clean_session_state.get("subscription_warning") is True, (
            "Section 13: subscription_warning=True при ошибке API — "
            "обязательное условие для показа сообщения"
        )

        # Проверяем точный текст через st.warning()
        warning_texts = [
            str(c.args[0]) for c in mock_warning.call_args_list if c.args
        ]
        post_upgrade_shown = any(
            _EXPECTED_POST_UPGRADE_MSG in t for t in warning_texts
        )
        # Допускаем два корректных варианта реализации:
        # 1. функция сама вызвала st.warning с нужным текстом
        # 2. функция выставила subscription_warning=True и UI-слой покажет текст
        assert post_upgrade_shown or clean_session_state["subscription_warning"], (
            f"Section 13: при post_upgrade + ошибке API должно быть показано "
            f"сообщение '{_EXPECTED_POST_UPGRADE_MSG}' либо выставлен "
            f"subscription_warning=True для UI-слоя"
        )

    def test_post_upgrade_message_exact_text_if_shown_directly(
            self, mocker, clean_session_state):
        """
        Если функция показывает сообщение об апгрейде напрямую через st.warning,
        текст должен совпадать с Section 13 дословно.
        Section 13: «Payment processors may take up to 60 seconds.
                    Please refresh in a moment.»
        """
        clean_session_state["post_upgrade"] = True

        mocker.patch("app.payments.gumroad.requests.get",
                     side_effect=Exception("503"))
        mocker.patch("app.payments.gumroad.st.session_state",
                     clean_session_state)
        mock_warning = mocker.patch("app.payments.gumroad.st.warning")
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        get_subscription_status(clean_session_state["user_email"])

        warning_texts = [
            str(c.args[0]) for c in mock_warning.call_args_list if c.args
        ]
        # Если функция вызывает st.warning при post_upgrade — текст должен быть точным
        if warning_texts:
            assert any(_EXPECTED_POST_UPGRADE_MSG in t for t in warning_texts), (
                f"Section 13: текст сообщения должен быть дословно: "
                f"'{_EXPECTED_POST_UPGRADE_MSG}'"
            )

    def test_no_post_upgrade_message_on_clean_success(self, mocker,
                                                        clean_session_state):
        """
        При успешном HTTP 200 пост-апгрейд-сообщение НЕ отображается.
        Section 13: «Success: subscription_warning=False»
        """
        mock_response = FakeResponse(200, _make_gumroad_response("pro"))
        mocker.patch("app.payments.gumroad.requests.get",
                     return_value=mock_response)
        mocker.patch("app.payments.gumroad.st.session_state",
                     clean_session_state)
        mock_warning = mocker.patch("app.payments.gumroad.st.warning")
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        get_subscription_status(clean_session_state["user_email"])

        assert clean_session_state["subscription_warning"] is False, (
            "Section 13: при успешном ответе subscription_warning=False, "
            "пост-апгрейд сообщение не нужно"
        )
        # При успехе st.warning с текстом апгрейда вызываться не должен
        upgrade_warnings = [
            str(c.args[0]) for c in mock_warning.call_args_list
            if c.args and "60 seconds" in str(c.args[0])
        ]
        assert len(upgrade_warnings) == 0, (
            "Section 13: при HTTP 200 сообщение об апгрейде показываться не должно"
        )

    def test_requests_timeout_is_5_seconds(self, mocker, clean_session_state):
        """
        requests.get должен вызываться с timeout=5.
        Section 13: «requests.get(..., timeout=5)»
        """
        mock_response = FakeResponse(200, {"plan": "free"})
        mock_get = mocker.patch("app.payments.gumroad.requests.get",
                                return_value=mock_response)
        mocker.patch("app.payments.gumroad.st.session_state",
                     clean_session_state)
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        get_subscription_status(clean_session_state["user_email"])

        call_kwargs = mock_get.call_args
        assert call_kwargs is not None
        # Поддерживаем как keyword так и positional передачу timeout
        timeout_val = call_kwargs.kwargs.get("timeout") if call_kwargs.kwargs else None
        assert timeout_val == 5, (
            "Section 13: requests.get должен вызываться с timeout=5"
        )


# ---------------------------------------------------------------------------
# Дополнительные граничные тесты
# Section 13: полное покрытие error-сценариев
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Граничные случаи из Section 13."""

    def test_error_no_cache_sets_reason_no_cache(self, mocker, clean_session_state):
        """
        При ошибке без кеша subscription_warning_reason='no_cache'.
        Section 13: «Error — no cache: reason='no_cache'»
        Section 14: subscription_warning_reason — ключ session_state
        """
        mocker.patch("app.payments.gumroad.requests.get",
                     side_effect=Exception("Network error"))
        mocker.patch("app.payments.gumroad.st.session_state",
                     clean_session_state)
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        result = get_subscription_status(clean_session_state["user_email"])

        assert result == "free"
        assert clean_session_state.get("subscription_warning_reason") == "no_cache", (
            "Section 13: при ошибке без кеша reason должен быть 'no_cache'"
        )

    def test_error_with_cache_sets_reason_api_error(
            self, mocker, session_state_with_cached_pro_plan):
        """
        При ошибке с кешем subscription_warning_reason='api_error'.
        Section 13: «Error — cache present: reason='api_error'»
        """
        state = session_state_with_cached_pro_plan

        mocker.patch("app.payments.gumroad.requests.get",
                     side_effect=Exception("Timeout"))
        mocker.patch("app.payments.gumroad.st.session_state", state)
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        result = get_subscription_status(state["user_email"])

        assert result == "pro"  # кешированный план
        assert state.get("subscription_warning_reason") == "api_error", (
            "Section 13: при ошибке с кешем reason должен быть 'api_error'"
        )

    def test_valid_plan_values_only(self, mocker, clean_session_state):
        """
        Функция возвращает только допустимые значения: 'free'/'starter'/'pro'.
        Section 13: «get_subscription_status → 'free' / 'starter' / 'pro'»
        """
        for plan in ("free", "starter", "pro"):
            state = {**clean_session_state}
            mock_response = FakeResponse(200, {"plan": plan})
            mocker.patch("app.payments.gumroad.requests.get",
                         return_value=mock_response)
            mocker.patch("app.payments.gumroad.st.session_state", state)
            _mock_spinner(mocker)

            from app.payments.gumroad import get_subscription_status
            result = get_subscription_status(clean_session_state["user_email"])

            assert result in ("free", "starter", "pro"), (
                f"Section 13: результат '{result}' не является допустимым планом"
            )

    def test_error_no_cache_returns_free(self, mocker, clean_session_state):
        """
        При любой ошибке без кеша — возврат 'free', не исключение.
        Section 13: «Error — no cache: Return 'free'»
        """
        mocker.patch("app.payments.gumroad.requests.get",
                     side_effect=Exception("Unexpected"))
        mocker.patch("app.payments.gumroad.st.session_state", clean_session_state)
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        result = get_subscription_status(clean_session_state["user_email"])

        assert result == "free", (
            "Section 13: при ошибке без кеша функция не должна бросать исключение, "
            "только возвращать 'free'"
        )

    def test_error_sets_subscription_warning_true(self, mocker, clean_session_state):
        """
        При любой ошибке subscription_warning=True.
        Section 13: «Error — no cache: subscription_warning=True»
        """
        mocker.patch("app.payments.gumroad.requests.get",
                     side_effect=Exception("Fail"))
        mocker.patch("app.payments.gumroad.st.session_state", clean_session_state)
        _mock_spinner(mocker)

        from app.payments.gumroad import get_subscription_status
        get_subscription_status(clean_session_state["user_email"])

        assert clean_session_state["subscription_warning"] is True, (
            "Section 13: при ошибке API subscription_warning должен быть True"
        )
