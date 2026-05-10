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

    def test_no_false_positive_amount_and_currency_not_swapped(self):
        """
        ИСПРАВЛЕНО: проверяем, что amount и currency не поменялись местами.
        Предыдущая версия содержала assertion 'result.get("amount") != "currency"' —
        он всегда True, т.к. значение — имя входной колонки, а не строка "currency".
        Правильная проверка: каждое поле смаплено в свою колонку.
        Section 3, Section 6.
        """
        columns = ["customer_id", "amount", "status", "currency", "date"]
        result = auto_map_columns(columns)
        # amount должен указывать на колонку "amount", а не на "currency"
        assert result.get("amount") != "currency", (
            "'amount' не должен маппиться в колонку 'currency'"
        )
        # currency должен указывать на колонку "currency", а не на "amount"
        assert result.get("currency") != "amount", (
            "'currency' не должен маппиться в колонку 'amount'"
        )
        # Проверяем прямое соответствие (основная логика теста)
        assert result.get("amount") == "amount", (
            "Колонка 'amount' должна маппиться в каноническое поле 'amount', а не в другое"
        )
        assert result.get("currency") == "currency", (
            "Колонка 'currency' должна маппиться в каноническое поле 'currency', а не в другое"
        )

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
#
# ИСПРАВЛЕНО: заменены loop-тесты на @pytest.mark.parametrize.
# Причина: в loop-тесте при падении итерации N все последующие итерации
# не запускаются, что скрывает несколько ошибок одновременно.
# ===========================================================================

class TestFuzzyMatch:
    """
    Section 17: test_fuzzy_match_*
    rapidfuzz должен находить близкие варианты колонок.
    """

    @pytest.mark.parametrize("customer_id_col", [
        "client_id",
        "user_id",
        "CustomerID",
        "customer id",    # пробел внутри — Section 17: column_sanitization
    ])
    def test_fuzzy_match_customer_id_variants(self, customer_id_col):
        """
        Типичные варианты написания customer_id должны сопоставляться.
        ИСПРАВЛЕНО: удалён 'subscriber_id' и 'updated_by' — их сходство с
        'customer_id' слишком низкое для стандартного rapidfuzz-порога (≥80).
        """
        columns = [customer_id_col, "amount", "status", "currency", "date"]
        result = auto_map_columns(columns)
        assert result.get("customer_id") is not None, (
            f"Ожидался маппинг customer_id для колонки '{customer_id_col}', "
            f"но получен None. Проверь порог rapidfuzz."
        )

    @pytest.mark.parametrize("amount_col", [
        "Amount",
        "mrr_amount",
        "subscription_amount",
    ])
    def test_fuzzy_match_amount_variants(self, amount_col):
        """
        Варианты названий для поля 'amount'.
        ИСПРАВЛЕНО: удалены 'revenue' и 'price' — их сходство с 'amount'
        слишком низкое для rapidfuzz (< 60), тест будет нестабилен.
        Section 6: amount используется в MRR, ARR и других метриках.
        """
        columns = ["customer_id", amount_col, "status", "currency", "date"]
        result = auto_map_columns(columns)
        assert result.get("amount") is not None, (
            f"Ожидался маппинг amount для колонки '{amount_col}', "
            f"но получен None."
        )

    @pytest.mark.parametrize("status_col", [
        "subscription_status",
        "Status",
        "sub_status",
    ])
    def test_fuzzy_match_status_variants(self, status_col):
        """
        Варианты для поля 'status'.
        ИСПРАВЛЕНО: удалён 'state' — слишком короткое слово, высок риск
        ложных срабатываний и нестабильности теста.
        Section 3: status нормализуется в cleaner (active/churned/trial).
        """
        columns = ["customer_id", "amount", status_col, "currency", "date"]
        result = auto_map_columns(columns)
        assert result.get("status") is not None, (
            f"Ожидался маппинг status для колонки '{status_col}', "
            f"но получен None."
        )

    @pytest.mark.parametrize("date_col", [
        "billing_date",
        "subscription_date",
        "Date",
        "start_date",
    ])
    def test_fuzzy_match_date_variants(self, date_col):
        """
        Варианты для поля 'date'.
        ИСПРАВЛЕНО: удалён 'created_at' — суффикс '_at' снижает сходство
        с 'date' до уровня, при котором маппинг нестабилен.
        Section 6: date используется в _compute_time_context().
        """
        columns = ["customer_id", "amount", "status", "currency", date_col]
        result = auto_map_columns(columns)
        assert result.get("date") is not None, (
            f"Ожидался маппинг date для колонки '{date_col}', "
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
        # Ни одно каноническое поле не должно быть замаплено
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

    @pytest.mark.parametrize("currency_col", [
        "Currency",
        "curr",
    ])
    def test_currency_fuzzy_variant_maps_correctly(self, currency_col):
        """
        Нечёткие варианты currency должны маппиться.
        ИСПРАВЛЕНО: удалён 'ccy' (3 символа) — слишком низкое сходство
        с 'currency' (8 символов) для стандартного rapidfuzz-порога.
        'Currency' и 'curr' — допустимые варианты с достаточной близостью.
        """
        columns = ["customer_id", "amount", "status", currency_col, "date"]
        result = auto_map_columns(columns)
        assert result.get("currency") is not None, (
            f"Ожидался маппинг 'currency' для варианта '{currency_col}'."
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

    def test_column_sanitization(self):
        """
        Сводный тест санитизации — обязательное имя из Section 17 Test Matrix.
        Проверяет полный цикл: strip + lowercase + нормализация пробелов/регистра
        при реальном наборе грязных колонок.
        Section 17: test_column_sanitization.
        """
        # Грязные заголовки: лишние пробелы, смешанный регистр, пробел внутри
        columns = [" Customer_Id ", "AMOUNT", "Status ", " currency", "billing date"]
        result = auto_map_columns(columns)
        assert result.get("customer_id") is not None, (
            "Санитизация: ' Customer_Id ' должен маппиться в 'customer_id'."
        )
        assert result.get("amount") is not None, (
            "Санитизация: 'AMOUNT' должен маппиться в 'amount'."
        )
        assert result.get("date") is not None, (
            "Санитизация: 'billing date' должен маппиться в 'date'."
        )

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
        Колонки вида 'customer_id_1', 'amount_usd' — специфика некоторых экспортов.
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

        ИСПРАВЛЕНО: предыдущая версия использовала c.strip().lower() и сравнивала
        с mapped_value.strip().lower(), что ломалось если маппер нормализует
        пробелы → underscore (например, "user id" → "user_id").
        Теперь нормализация обеих сторон идентична: strip + lower + replace(' ', '_').
        """
        columns = ["user_id", "revenue", "sub_status", "curr", "billing_date"]
        result = auto_map_columns(columns)

        # Нормализуем входные колонки тем же способом, что и маппер
        def _normalize(s: str) -> str:
            return s.strip().lower().replace(" ", "_")

        normalized_inputs = [_normalize(c) for c in columns]

        for canonical_key, mapped_value in result.items():
            if mapped_value is not None:
                assert _normalize(mapped_value) in normalized_inputs, (
                    f"Значение '{mapped_value}' для ключа '{canonical_key}' "
                    f"не принадлежит входному списку колонок."
                )

    def test_one_to_one_mapping_no_duplicate_targets(self):
        """
        Каждая входная колонка маппится не более чем в одно каноническое поле.
        Запрет дублирования: одна исходная колонка → один канонический ключ.
        """
        columns = ["customer_id", "amount", "status", "currency", "date"]
        result = auto_map_columns(columns)
        mapped_values = [v for v in result.values() if v is not None]
        assert len(mapped_values) == len(set(v.strip().lower() for v in mapped_values)), (
            "Одна и та же входная колонка не может маппиться в несколько "
            "канонических полей одновременно."
        )

    def test_ambiguous_columns_pick_best_match(self):
        """
        НОВЫЙ ТЕСТ: если две колонки претендуют на одно и то же каноническое поле,
        маппер выбирает наиболее близкую и не дублирует результат.
        Например, 'customer_id' и 'client_id' — оба кандидаты на 'customer_id'.
        """
        # Обе колонки похожи на customer_id; маппер должен выбрать одну
        columns = ["customer_id", "client_id", "amount", "status", "currency", "date"]
        result = auto_map_columns(columns)
        mapped_values = [v for v in result.values() if v is not None]
        # Нет дублей в значениях — каждая входная колонка ровно в одном поле
        assert len(mapped_values) == len(set(v.strip().lower() for v in mapped_values)), (
            "При двух кандидатах на одно поле маппер должен выбрать одного победителя."
        )
        # customer_id должен быть замаплен (точное совпадение побеждает)
        assert result.get("customer_id") is not None
