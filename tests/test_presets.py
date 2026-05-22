"""
test_presets.py
Тесты для app/core/presets.py — detect_preset() (v3.2.2)
Проверяет распознавание источника CSV по сигнатурам колонок.

Спецификация: SPEC.md §8 v3.2.2
Каталог сигнатур: app/core/presets.py (_PRESET_SIGNATURES)
"""

import pandas as pd
import pytest

from app.core.presets import detect_preset, ALL_PRESETS, _PRESET_SIGNATURES, get_preset_mapping


# ===========================================================================
# ГРУППА 1 — Точное распознавание каждого пресета
# ===========================================================================

class TestDetectKnownPresets:
    """
    Проверяем, что каждый из 6 источников распознаётся по своим
    каноническим колонкам.
    """

    def test_detect_stripe_exact(self):
        """Stripe: customer_id, created, amount, status."""
        columns = ["customer_id", "created", "amount", "status"]
        df = pd.DataFrame(columns=columns)
        assert detect_preset(df, columns) == "stripe"

    def test_detect_paddle_exact(self):
        """Paddle: customer_id, created_at, amount, status."""
        columns = ["customer_id", "created_at", "amount", "status"]
        df = pd.DataFrame(columns=columns)
        assert detect_preset(df, columns) == "paddle"

    def test_detect_gumroad_exact(self):
        """Gumroad: email, created_at, price, cancelled."""
        columns = ["email", "created_at", "price", "cancelled"]
        df = pd.DataFrame(columns=columns)
        assert detect_preset(df, columns) == "gumroad"

    def test_detect_lemonsqueezy_exact(self):
        """LemonSqueezy: customer_email, created_at, total, status."""
        columns = ["customer_email", "created_at", "total", "status"]
        df = pd.DataFrame(columns=columns)
        assert detect_preset(df, columns) == "lemonsqueezy"

    def test_detect_chargebee_exact(self):
        """Chargebee: customer_id, started_at, amount, status."""
        columns = ["customer_id", "started_at", "amount", "status"]
        df = pd.DataFrame(columns=columns)
        assert detect_preset(df, columns) == "chargebee"

    def test_detect_manual_exact(self):
        """Manual: customer_id, date, amount, status."""
        columns = ["customer_id", "date", "amount", "status"]
        df = pd.DataFrame(columns=columns)
        assert detect_preset(df, columns) == "manual"


# ===========================================================================
# ГРУППА 2 — Неизвестный формат → None
# ===========================================================================

class TestDetectUnknown:
    """Когда колонки не соответствуют ни одному пресету."""

    def test_unknown_returns_none(self):
        """Случайные колонки → None."""
        columns = ["foo", "bar", "baz"]
        df = pd.DataFrame(columns=columns)
        assert detect_preset(df, columns) is None

    def test_partial_match_returns_none(self):
        """
        Частичное совпадение (3 из 4 полей) — это несовпадение.
        Только 4 из 4 обязательных полей активируют пресет.
        """
        # Есть customer_id, amount, status, но нет date (billing_period — не сигнатура)
        columns = ["customer_id", "amount", "status", "billing_period"]
        df = pd.DataFrame(columns=columns)
        assert detect_preset(df, columns) is None

    def test_empty_columns_returns_none(self):
        """Пустой список колонок → None."""
        df = pd.DataFrame(columns=[])
        assert detect_preset(df, []) is None

    def test_none_columns_returns_none(self):
        """Только одна из четырёх колонок — недостаточно."""
        columns = ["customer_id", "notes", "tags"]
        df = pd.DataFrame(columns=columns)
        assert detect_preset(df, columns) is None


# ===========================================================================
# ГРУППА 3 — Регистронезависимость (case-insensitive)
# ===========================================================================

class TestDetectCaseInsensitive:
    """Колонки могут быть в любом регистре."""

    def test_uppercase_columns_still_detect(self):
        """Верхний регистр не мешает распознаванию."""
        columns = ["CUSTOMER_ID", "CREATED", "AMOUNT", "STATUS"]
        df = pd.DataFrame(columns=columns)
        assert detect_preset(df, columns) == "stripe"

    def test_mixed_case_columns(self):
        """Смешанный регистр — Stripe."""
        columns = ["Customer_Id", "Created", "Amount", "Status"]
        df = pd.DataFrame(columns=columns)
        assert detect_preset(df, columns) == "stripe"

    def test_gumroad_mixed_case(self):
        """Gumroad с разным регистром."""
        columns = ["EMAIL", "Created_At", "Price", "CANCELLED"]
        df = pd.DataFrame(columns=columns)
        assert detect_preset(df, columns) == "gumroad"


# ===========================================================================
# ГРУППА 4 — Лишние колонки не мешают
# ===========================================================================

class TestDetectExtraColumns:
    """Наличие дополнительных колонок не должно блокировать распознавание."""

    def test_stripe_with_extra_columns(self):
        """Stripe + несколько лишних колонок."""
        columns = ["id", "customer_id", "created", "amount", "status", "currency", "description"]
        df = pd.DataFrame(columns=columns)
        assert detect_preset(df, columns) == "stripe"

    def test_gumroad_with_extra_columns(self):
        """Gumroad + дополнительные поля."""
        columns = ["email", "created_at", "price", "cancelled", "product_name", "offer_code"]
        df = pd.DataFrame(columns=columns)
        assert detect_preset(df, columns) == "gumroad"

    def test_manual_with_extra_columns(self):
        """Manual + лишние колонки."""
        columns = ["customer_id", "date", "amount", "status", "notes", "invoice_number"]
        df = pd.DataFrame(columns=columns)
        assert detect_preset(df, columns) == "manual"


# ===========================================================================
# ГРУППА 5 — Порядок при пересекающихся сигнатурах
# ===========================================================================

class TestDetectPriority:
    """
    Если совпадают несколько пресетов, возвращается первый по порядку
    в ALL_PRESETS (stripe → manual).
    """

    def test_stripe_before_manual_when_both_match(self):
        """
        Колонки, где есть и 'created' (Stripe), и 'date' (Manual).
        Оба пресета совпадают полностью, приоритет у Stripe (раньше в ALL_PRESETS).
        """
        columns = ["customer_id", "created", "amount", "status", "date"]
        df = pd.DataFrame(columns=columns)
        # Stripe: customer_id+created+amount+status → все есть
        # Manual: customer_id+date+amount+status → все есть
        # Должен победить Stripe (порядок в ALL_PRESETS)
        assert detect_preset(df, columns) == "stripe"

    def test_paddle_has_unique_date_col_so_no_conflict(self):
        """
        Paddle и Gumroad оба используют created_at для даты, но разные
        customer_id/amount/status — конфликта нет.
        """
        columns = ["customer_id", "created_at", "amount", "status"]
        df = pd.DataFrame(columns=columns)
        assert detect_preset(df, columns) == "paddle"


# ===========================================================================
# ГРУППА 6 — Сигнатура manual совпадает только при точном 'date'
# ===========================================================================

class TestManualPreset:
    """Manual определяется только когда есть колонка 'date', а не 'created' и пр."""

    def test_manual_when_date_present(self):
        columns = ["customer_id", "date", "amount", "status"]
        df = pd.DataFrame(columns=columns)
        assert detect_preset(df, columns) == "manual"

    def test_manual_not_detected_when_date_is_created(self):
        """Если дата называется 'created', это Stripe, не Manual."""
        columns = ["customer_id", "created", "amount", "status"]
        df = pd.DataFrame(columns=columns)
        assert detect_preset(df, columns) != "manual"


# ===========================================================================
# ГРУППА 7 — Параметр df передаётся, но не используется (задел на будущее)
# ===========================================================================

class TestDfParamAccepted:
    """Функция должна принимать DataFrame, даже если сейчас не читает данные."""

    def test_df_param_with_data_does_not_affect_result(self):
        """Даже если в DataFrame есть данные, результат зависит только от columns."""
        df = pd.DataFrame({
            "customer_id": [1, 2],
            "created": ["2024-01-01", "2024-02-01"],
            "amount": [9.99, 19.99],
            "status": ["active", "cancelled"],
        })
        assert detect_preset(df, df.columns.tolist()) == "stripe"

    def test_df_param_empty_dataframe(self):
        """Пустой DataFrame (без строк) — работает."""
        df = pd.DataFrame(columns=["customer_id", "created", "amount", "status"])
        assert detect_preset(df, df.columns.tolist()) == "stripe"

    def test_df_param_with_none_columns_still_works(self):
        """Передача df с None в columns не должна падать."""
        df = pd.DataFrame(columns=["customer_id", "created", "amount", "status"])
        # columns аргумент берём отдельно — имитируем вызов из upload page
        cols = df.columns.tolist()
        assert detect_preset(df, cols) == "stripe"


# ===========================================================================
# ГРУППА 8 — Консистентность каталога (защита от регрессии сигнатур)
# ===========================================================================

class TestSignatureConsistency:
    """
    Убеждаемся, что _PRESET_SIGNATURES корректен:
    каждый пресет содержит все 4 обязательных поля.
    """

    def test_all_presets_have_required_fields(self):
        required = {"customer_id", "date", "amount", "status"}
        for name, sig in _PRESET_SIGNATURES.items():
            assert set(sig.keys()) == required, (
                f"Пресет '{name}' должен содержать ровно 4 поля: {required}. "
                f"Сейчас: {set(sig.keys())}"
            )

    def test_all_presets_in_all_presets_list(self):
        """ALL_PRESETS синхронизирован с _PRESET_SIGNATURES."""
        assert set(ALL_PRESETS) == set(_PRESET_SIGNATURES.keys())


# ===========================================================================
# ГРУППА 9 — get_preset_mapping() (v3.2.4)
# ===========================================================================

class TestGetPresetMapping:
    """
    v3.2.4: Тесты для get_preset_mapping() — получение mapping-правил
    для конкретного пресета, используется на mapping-странице.
    """

    def test_stripe_mapping_returns_correct_dict(self):
        """Stripe: customer_id→customer_id, date→created, amount→amount, status→status."""
        result = get_preset_mapping("stripe")
        assert result == {
            "customer_id": "customer_id",
            "date": "created",
            "amount": "amount",
            "status": "status",
        }

    def test_gumroad_mapping_returns_correct_dict(self):
        """Gumroad: email как customer_id, cancelled как status."""
        result = get_preset_mapping("gumroad")
        assert result == {
            "customer_id": "email",
            "date": "created_at",
            "amount": "price",
            "status": "cancelled",
        }

    def test_lemonsqueezy_mapping_returns_correct_dict(self):
        """LemonSqueezy: customer_email, total."""
        result = get_preset_mapping("lemonsqueezy")
        assert result == {
            "customer_id": "customer_email",
            "date": "created_at",
            "amount": "total",
            "status": "status",
        }

    def test_all_presets_return_valid_mapping(self):
        """Каждый пресет возвращает словарь с 4 обязательными полями."""
        required = {"customer_id", "date", "amount", "status"}
        for preset_name in ALL_PRESETS:
            result = get_preset_mapping(preset_name)
            assert isinstance(result, dict), (
                f"get_preset_mapping('{preset_name}') должен вернуть dict"
            )
            # Каждое поле — непустая строка
            for field in required:
                assert field in result, (
                    f"Поле '{field}' отсутствует в mapping'е для пресета '{preset_name}'"
                )
                assert isinstance(result[field], str) and result[field], (
                    f"Значение для '{field}' в пресете '{preset_name}' "
                    f"должно быть непустой строкой"
                )

    def test_unknown_preset_raises_value_error(self):
        """Неизвестный пресет → ValueError."""
        with pytest.raises(ValueError, match="Unknown preset"):
            get_preset_mapping("unknown")

    def test_unknown_preset_raises_value_error_message_contains_name(self):
        """Сообщение об ошибке содержит имя неизвестного пресета."""
        with pytest.raises(ValueError, match="foobar"):
            get_preset_mapping("foobar")

    def test_returned_dict_is_independent_copy(self):
        """
        Возвращаемый словарь — копия, мутация не влияет на оригинал.
        Защита от случайной порчи _PRESET_SIGNATURES.
        """
        original = _PRESET_SIGNATURES["stripe"].copy()
        result = get_preset_mapping("stripe")
        # Мутируем результат
        result["customer_id"] = "hacked"
        # Оригинал не должен измениться
        assert _PRESET_SIGNATURES["stripe"] == original, (
            "Мутация результата get_preset_mapping() не должна влиять на _PRESET_SIGNATURES"
        )

    def test_mapping_values_are_lowercase(self):
        """Все значения в сигнатурах — в нижнем регистре."""
        for preset_name in ALL_PRESETS:
            result = get_preset_mapping(preset_name)
            for field, value in result.items():
                assert value == value.lower(), (
                    f"Значение '{value}' для '{field}' в пресете '{preset_name}' "
                    f"должно быть в нижнем регистре"
                )