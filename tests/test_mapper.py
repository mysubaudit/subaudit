"""
test_mapper.py
Тесты для app/core/mapper.py — auto_map_columns()
Строго по Master Specification Sheet v2.9, Section 17 (Test Matrix — test_mapper.py)
и Section 4 (mapper.py использует rapidfuzz).

Покрываемые тест-кейсы (Section 17):
  - test_no_false_positive_created_by
  - test_fuzzy_match_*  (несколько вариантов)
  - test_currency_missing_returns_none
  - test_column_sanitization

Зависимости (Section 15):
  - rapidfuzz==3.9.3  (НЕ fuzzywuzzy — deprecated)
  - pytest==8.2.2
  - pytest-mock==3.14.0
"""

import pytest
from unittest.mock import patch

# Импорт тестируемого модуля (Section 4: app/core/mapper.py)
from app.core.mapper import auto_map_columns


# ---------------------------------------------------------------------------
# Константы — канонические имена полей, ожидаемые спецификацией
# (Section 5: Core Definitions — customer_id, amount, status, currency, date)
# ---------------------------------------------------------------------------
CANONICAL_FIELDS = ("customer_id", "amount", "status", "currency", "date")


# ===========================================================================
# ГРУППА 1 — test_no_false_positive_created_by  (Section 17)
# Гарантируем, что "created_by" НЕ маппится в "customer_id"
# несмотря на лексическое сходство (rapidfuzz может дать высокий score).
# ===========================================================================

class TestNoFalsePositive:
    """
    Section 17: test_no_false_positive_created_by
    Колонка 'created_by' семантически НЕ является 'customer_id'.
    Маппер должен отклонить такое совпадение.
    """

    def test_no_false_positive_created_by(self):
        """
        'created_by' не должен быть сопоставлен с 'customer_id'.
        Section 17 — явно указан как обязательный кейс.
        """
        columns = ["created_by", "amount", "status", "currency", "date"]
        result = auto_map_columns(columns)
        # 'created_by' не является customer_id — ожидаем None
        assert result.get("customer_id") is None, (
            "Ложное срабатывание: 'created_by' не должен маппиться в 'customer_id'"
        )

    def test_no_false_positive_updated_by(self):
        """
        'updated_by' тоже не должен совпадать с 'customer_id'.
        Расширение логики из test_no_false_positive_created_by.
        """
        columns = ["updated_by", "revenue", "subscription_status", "currency", "billing_date"]
        result = auto_map_columns(columns)
        assert result.get("customer_id") is None, (
            "'updated_by' не должен маппиться в 'customer_id'"
        )

    def test_no_false_positive_amount_not_mapped_to_currency(self):
        """
        'amount' не должен маппиться в 'currency' — совершенно разные поля.
        Защита от кросс-фильдовых ложных срабатываний rapidfuzz.
        """
        columns = ["customer_id", "amount", "status", "currency", "date"]
        result = auto_map_columns(columns)
        # amount и currency должны быть сопоставлены корректно
        assert result.get("amount") != "currency"
        assert result.get("currency") != "amount"

    def test_no_false_positive_status_not_mapped_to_customer_id(self):
        """
        'status' не должен маппиться в 'customer_id'.
        """
        columns = ["status", "amount", "currency", "date"]
        result = auto_map_columns(columns)
        assert result.get("customer_id") is None


# ===========================================================================
# ГРУППА 2 — test_fuzzy_match_*  (Section 17)
# Проверяем, что rapidfuzz корректно сопоставляет реальные вариации названий.
# Section 15: rapidfuzz==3.9.3 — НЕ fuzzywuzzy.
# ===========================================================================

class TestFuzzyMatch:
    """
    Section 17: test_fuzzy_match_*
    rapidfuzz должен находить близкие варианты колонок.
    """

    def test_fuzzy_match_customer_id_variants(self):
        """
        Типичные варианты написания customer_id должны сопоставляться.
        """
        variants = [
            ["client_id", "amount", "status", "currency", "date"],
            ["user_id", "amount", "status", "currency", "date"],
            ["subscriber_id", "amount", "status", "currency", "date"],
            ["CustomerID", "amount", "status", "currency", "date"],
            ["customer id", "amount", "status", "currency", "date"],  # пробел — Section 17: column_sanitization
        ]
        for columns in variants:
            result = auto_map_columns(columns)
            assert result.get("customer_id") is not None, (
                f"Ожидался маппинг customer_id для колонки '{columns[0]}', "
                f"но получен None. Проверь порог rapidfuzz."
            )

    def test_fuzzy_match_amount_variants(self):
        """
        Варианты названий для поля 'amount'.
        Section 6: amount используется в MRR, ARR и других метриках.
        """
        variants = [
            ["customer_id", "revenue", "status", "currency", "date"],
            ["customer_id", "mrr_amount", "status", "currency", "date"],
            ["customer_id", "price", "status", "currency", "date"],
            ["customer_id", "Amount", "status", "currency", "date"],
            ["customer_id", "subscription_amount", "status", "currency", "date"],
        ]
        for columns in variants:
            result = auto_map_columns(columns)
            assert result.get("amount") is not None, (
                f"Ожидался маппинг amount для колонки '{columns[1]}', "
                f"но получен None."
            )

    def test_fuzzy_match_status_variants(self):
        """
        Варианты для поля 'status'.
        Section 3: status нормализуется в cleaner (active/churned/trial).
        """
        variants = [
            ["customer_id", "amount", "subscription_status", "currency", "date"],
            ["customer_id", "amount", "state", "currency", "date"],
            ["customer_id", "amount", "Status", "currency", "date"],
            ["customer_id", "amount", "sub_status", "currency", "date"],
        ]
        for columns in variants:
            result = auto_map_columns(columns)
            assert result.get("status") is not None, (
                f"Ожидался маппинг status для колонки '{columns[2]}', "
                f"но получен None."
            )

    def test_fuzzy_match_date_variants(self):
        """
        Варианты для поля 'date'.
        Section 6: date используется в _compute_time_context().
        """
        variants = [
            ["customer_id", "amount", "status", "currency", "billing_date"],
            ["customer_id", "amount", "status", "currency", "created_at"],
            ["customer_id", "amount", "status", "currency", "subscription_date"],
            ["customer_id", "amount", "status", "currency", "Date"],
            ["customer_id", "amount", "status", "currency", "start_date"],
        ]
        for columns in variants:
            result = auto_map_columns(columns)
            assert result.get("date") is not None, (
                f"Ожидался маппинг date для колонки '{columns[4]}', "
                f"но получен None."
            )

    def test_fuzzy_match_exact_names_always_match(self):
        """
        Точные совпадения должны всегда сопоставляться — базовый smoke-тест.
        """
        columns = ["customer_id", "amount", "status", "currency", "date"]
        result = auto_map_columns(columns)
        for field in CANONICAL_FIELDS:
            assert result.get(field) is not None, (
                f"Точное совпадение для '{field}' не сработало. "
                f"Критическая ошибка маппера."
            )

    def test_fuzzy_match_all_uppercase_columns(self):
        """
        Колонки в верхнем регистре — маппер должен быть регистронезависимым.
        Section 17: column_sanitization предполагает нормализацию регистра.
        """
        columns = ["CUSTOMER_ID", "AMOUNT", "STATUS", "CURRENCY", "DATE"]
        result = auto_map_columns(columns)
        assert result.get("customer_id") is not None
        assert result.get("amount") is not None
        assert result.get("status") is not None

    def test_fuzzy_match_does_not_map_unrelated_columns(self):
        """
        Совершенно несвязанные колонки не должны маппиться.
        Защита от чрезмерно агрессивного fuzzy-matching.
        """
        # Колонки без релевантных полей — только произвольные названия
        columns = ["notes", "comments", "tags", "region", "country"]
        result = auto_map_columns(columns)
        # Ни одно канонические поле не должно быть замаплено
        for field in CANONICAL_FIELDS:
            assert result.get(field) is None, (
                f"Ложное срабатывание: '{field}' сопоставлен с нерелевантной колонкой. "
                f"Снизь порог rapidfuzz или добавь блок-лист."
            )

    def test_fuzzy_match_returns_dict_with_all_canonical_keys(self):
        """
        Результат auto_map_columns() всегда является dict
        со всеми каноническими ключами (значение может быть None).
        Section 4: auto_map_columns() — rapidfuzz.
        """
        columns = ["customer_id", "amount", "status", "currency", "date"]
        result = auto_map_columns(columns)
        assert isinstance(result, dict), "auto_map_columns должна возвращать dict"
        for field in CANONICAL_FIELDS:
            assert field in result, (
                f"Ключ '{field}' отсутствует в результате auto_map_columns(). "
                f"Все канонические ключи должны присутствовать (значение может быть None)."
            )


# ===========================================================================
# ГРУППА 3 — test_currency_missing_returns_none  (Section 17)
# Section 3: currency — обязательное поле для обнаружения смешанных валют.
# Если поле не найдено — возвращаем None для ключа 'currency'.
# ===========================================================================

class TestCurrencyMissing:
    """
    Section 17: test_currency_missing_returns_none
    Section 3: Mixed currencies → show error, block processing.
    Если currency-колонку невозможно идентифицировать — маппер возвращает None.
    """

    def test_currency_missing_returns_none(self):
        """
        Если в CSV нет колонки, похожей на 'currency', возвращаем None.
        Section 17 — явно требуемый тест-кейс.
        """
        # Нет колонки, похожей на currency
        columns = ["customer_id", "amount", "status", "date"]
        result = auto_map_columns(columns)
        assert result.get("currency") is None, (
            "Ожидался None для 'currency' при отсутствии подходящей колонки."
        )

    def test_currency_present_maps_correctly(self):
        """
        Если currency-колонка есть — маппер её находит.
        Section 3: currency нужна для проверки mixed currencies.
        """
        columns = ["customer_id", "amount", "status", "currency", "date"]
        result = auto_map_columns(columns)
        assert result.get("currency") is not None, (
            "Ожидался маппинг 'currency' при наличии одноимённой колонки."
        )

    def test_currency_fuzzy_variant_maps_correctly(self):
        """
        Нечёткий вариант currency ('curr', 'ccy', 'Currency') должен маппиться.
        """
        fuzzy_variants = [
            ["customer_id", "amount", "status", "Currency", "date"],
            ["customer_id", "amount", "status", "curr", "date"],
            ["customer_id", "amount", "status", "ccy", "date"],
        ]
        for columns in fuzzy_variants:
            result = auto_map_columns(columns)
            assert result.get("currency") is not None, (
                f"Ожидался маппинг 'currency' для варианта '{columns[3]}'."
            )

    def test_currency_completely_absent_does_not_raise(self):
        """
        Отсутствие currency-колонки не должно вызывать исключение.
        Маппер возвращает None — обработка ошибки на уровне UI/cleaner.
        Section 3: cleaner проверяет mixed currencies — маппер только ищет.
        """
        columns = ["user_id", "revenue", "sub_status", "billing_date"]
        try:
            result = auto_map_columns(columns)
            assert isinstance(result, dict)
        except Exception as exc:
            pytest.fail(
                f"auto_map_columns не должна вызывать исключений при отсутствии currency. "
                f"Получено: {type(exc).__name__}: {exc}"
            )

    def test_all_fields_missing_returns_all_none(self):
        """
        Если ни одно поле не идентифицировано — все значения в dict равны None.
        """
        columns = ["foo", "bar", "baz", "qux", "quux"]
        result = auto_map_columns(columns)
        for field in CANONICAL_FIELDS:
            assert result.get(field) is None, (
                f"Ожидался None для '{field}' при полностью нераспознанных колонках."
            )


# ===========================================================================
# ГРУППА 4 — test_column_sanitization  (Section 17)
# Маппер должен нормализовывать названия колонок перед сравнением:
#   - strip whitespace
#   - lowercase
#   - replace spaces/special chars с underscore (или аналог)
# ===========================================================================

class TestColumnSanitization:
    """
    Section 17: test_column_sanitization
    Нормализация входных колонок перед fuzzy-matching через rapidfuzz.
    """

    def test_column_with_leading_trailing_whitespace(self):
        """
        Колонки с пробелами по краям должны корректно сопоставляться.
        """
        columns = [" customer_id ", " amount ", " status ", " currency ", " date "]
        result = auto_map_columns(columns)
        assert result.get("customer_id") is not None, (
            "Пробелы в начале/конце колонки не должны ломать маппинг."
        )
        assert result.get("amount") is not None

    def test_column_with_internal_spaces(self):
        """
        Колонки вида 'customer id' (пробел внутри) должны маппиться.
        """
        columns = ["customer id", "amount", "status", "currency", "date"]
        result = auto_map_columns(columns)
        assert result.get("customer_id") is not None, (
            "'customer id' (с пробелом) должен маппиться в 'customer_id'."
        )

    def test_column_mixed_case_sanitized(self):
        """
        Колонки в смешанном регистре нормализуются перед matching.
        """
        columns = ["Customer_Id", "Amount", "Status", "Currency", "Date"]
        result = auto_map_columns(columns)
        assert result.get("customer_id") is not None
        assert result.get("amount") is not None
        assert result.get("status") is not None
        assert result.get("currency") is not None
        assert result.get("date") is not None

    def test_column_with_special_characters(self):
        """
        Спецсимволы в названии колонки (дефис, точка, скобки) обрабатываются без краша.
        """
        columns = ["customer-id", "amount.usd", "status(sub)", "currency", "date"]
        # Не обязательно успешно маппятся, но НЕ должны вызывать исключение
        try:
            result = auto_map_columns(columns)
            assert isinstance(result, dict)
        except Exception as exc:
            pytest.fail(
                f"auto_map_columns не должна падать на спецсимволах. "
                f"Получено: {type(exc).__name__}: {exc}"
            )

    def test_column_with_numeric_suffix(self):
        """
        Колонки вида 'customer_id_1', 'amount_2' — специфика некоторых экспортов.
        Маппер должен обрабатывать без исключений.
        """
        columns = ["customer_id_1", "amount_usd", "status", "currency", "date"]
        try:
            result = auto_map_columns(columns)
            assert isinstance(result, dict)
        except Exception as exc:
            pytest.fail(
                f"auto_map_columns не должна падать на колонках с суффиксами. "
                f"Получено: {type(exc).__name__}: {exc}"
            )

    def test_empty_column_list_returns_all_none(self):
        """
        Пустой список колонок — все поля None, без исключений.
        """
        result = auto_map_columns([])
        assert isinstance(result, dict)
        for field in CANONICAL_FIELDS:
            assert result.get(field) is None, (
                f"Ожидался None для '{field}' при пустом списке колонок."
            )

    def test_duplicate_columns_do_not_cause_error(self):
        """
        Дублированные колонки (редкий кейс некоторых CSV) не должны вызывать краш.
        """
        columns = ["customer_id", "customer_id", "amount", "status", "currency", "date"]
        try:
            result = auto_map_columns(columns)
            assert isinstance(result, dict)
        except Exception as exc:
            pytest.fail(
                f"Дубликаты колонок не должны ломать auto_map_columns. "
                f"Получено: {type(exc).__name__}: {exc}"
            )

    def test_sanitization_preserves_correct_mapping_after_normalization(self):
        """
        После санитизации маппинг должен быть стабильным и воспроизводимым.
        Вызов auto_map_columns дважды с одним входом → одинаковый результат.
        Section 4: auto_map_columns() — детерминированная функция.
        """
        columns = ["Customer_ID", "AMOUNT", "Status", "currency", "Date"]
        result_1 = auto_map_columns(columns)
        result_2 = auto_map_columns(columns)
        assert result_1 == result_2, (
            "auto_map_columns должна быть детерминированной: "
            "одинаковый вход → одинаковый выход."
        )


# ===========================================================================
# ГРУППА 5 — Дополнительные интеграционные тесты
# Проверяем поведение маппера на реальных fixture-данных (Section 17 fixtures).
# ===========================================================================

class TestMapperIntegration:
    """
    Интеграционные тесты, имитирующие реальные CSV-заголовки из фикстур.
    Section 17 fixtures: sample_basic.csv, sample_reactivation.csv и др.
    """

    def test_sample_basic_csv_columns_map_completely(self):
        """
        Заголовки из sample_basic.csv (Section 17 fixtures) полностью маппятся.
        500 строк, USD, 12 месяцев, чистые данные — happy path.
        """
        # Типичный набор колонок «чистого» CSV
        columns = ["customer_id", "amount", "status", "currency", "date"]
        result = auto_map_columns(columns)
        for field in CANONICAL_FIELDS:
            assert result.get(field) is not None, (
                f"Все поля должны сопоставляться для базового набора колонок. "
                f"Поле '{field}' не найдено."
            )

    def test_mapper_output_values_are_strings_or_none(self):
        """
        Значения в dict — строки (имя колонки из входного списка) или None.
        Не допускаются числа, списки, bool и прочее.
        """
        columns = ["customer_id", "amount", "status", "currency", "date"]
        result = auto_map_columns(columns)
        for canonical_key, mapped_value in result.items():
            assert mapped_value is None or isinstance(mapped_value, str), (
                f"Значение для '{canonical_key}' должно быть str или None, "
                f"получено: {type(mapped_value)}"
            )

    def test_mapped_value_exists_in_input_columns(self):
        """
        Возвращаемое значение маппинга обязано быть одним из входных столбцов
        (или None). Маппер не придумывает новых имён.
        """
        columns = ["user_id", "revenue", "sub_status", "curr", "billing_date"]
        result = auto_map_columns(columns)
        sanitized_inputs = [c.strip().lower() for c in columns]
        for canonical_key, mapped_value in result.items():
            if mapped_value is not None:
                assert mapped_value.strip().lower() in sanitized_inputs, (
                    f"Значение '{mapped_value}' для ключа '{canonical_key}' "
                    f"не принадлежит входному списку колонок."
                )

    def test_one_to_one_mapping_no_duplicate_targets(self):
        """
        Каждая входная колонка маппится не более чем в одно канонического поле.
        Запрет дублирования: одна исходная колонка → один канонический ключ.
        """
        columns = ["customer_id", "amount", "status", "currency", "date"]
        result = auto_map_columns(columns)
        mapped_values = [v for v in result.values() if v is not None]
        assert len(mapped_values) == len(set(mapped_values)), (
            "Одна и та же входная колонка не может маппиться в несколько "
            "канонических полей одновременно."
        )
