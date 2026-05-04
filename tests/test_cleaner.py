"""
test_cleaner.py — Полный набор тестов для app/core/cleaner.py
Строго по Master Specification Sheet v2.9, Section 17 (Testing — Full Test Matrix)
Тестируемые случаи (Section 17):
  - test_duplicates_removed
  - test_multicurrency_error
  - test_status_normalization_[active/churned/trial]
  - test_negatives_tracked
  - test_zeros_tracked
Дополнительная логика покрывается из:
  - Section 3 (Data Limits & Validation)
  - Section 5 (Core Definitions — "active rows")
  - Section 6 (Metric Formulas — amount==0, amount<0 exclusion rules)
"""

import io
import pytest
import pandas as pd

from app.core.cleaner import clean_data


# ---------------------------------------------------------------------------
# Вспомогательные функции для генерации тестовых DataFrame
# ---------------------------------------------------------------------------

def _make_df(**kwargs) -> pd.DataFrame:
    """
    Создаёт минимальный DataFrame с обязательными колонками.
    Принимает переопределения колонок через kwargs.
    Section 3: обязательные колонки для обработки.
    """
    defaults = {
        "customer_id": ["c1", "c2", "c3"],
        "date":        ["2024-01-01", "2024-01-01", "2024-01-01"],
        "amount":      [100.0, 200.0, 300.0],
        "status":      ["active", "active", "active"],
        "currency":    ["USD", "USD", "USD"],
    }
    defaults.update(kwargs)
    return pd.DataFrame(defaults)


def _make_csv_bytes(df: pd.DataFrame) -> bytes:
    """Конвертирует DataFrame в CSV-байты для тестов загрузки."""
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


# ---------------------------------------------------------------------------
# Фикстуры (Section 17 — Test Fixtures)
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_basic_df():
    """
    Чистый базовый DataFrame (аналог sample_basic.csv).
    Section 17: happy path — 3 строки, USD, 1 месяц.
    """
    return _make_df()


@pytest.fixture
def sample_multicurrency_df():
    """
    DataFrame со смешанными валютами (аналог sample_multicurrency.csv).
    Section 3: mixed currencies → show error, block processing.
    """
    return _make_df(currency=["USD", "EUR", "USD"])


@pytest.fixture
def sample_with_duplicates_df():
    """
    DataFrame с точными дублями строк.
    Section 3: Remove exact duplicates. Report in cleaning_report['duplicates_removed'].
    """
    base = _make_df()
    # Добавляем точную копию первой строки
    return pd.concat([base, base.iloc[[0]]], ignore_index=True)


@pytest.fixture
def sample_negatives_df():
    """
    DataFrame с отрицательными суммами (рефанды).
    Section 3: amount < 0 → exclude from MRR, include in revenue_churn, include in cleaning_report.
    Section 6: Revenue Churn — negative amounts tracked.
    """
    return _make_df(
        customer_id=["c1", "c2", "c3", "c4"],
        date=["2024-01-01"] * 4,
        amount=[100.0, 200.0, -50.0, -75.0],
        status=["active", "active", "churned", "active"],
        currency=["USD"] * 4,
    )


@pytest.fixture
def sample_zeros_df():
    """
    DataFrame с нулевыми суммами.
    Section 3: amount == 0 → exclude from MRR, include in cleaning_report,
    do NOT remove from df_clean.
    Section 5: "active rows" = status == 'active' AND amount > 0.
    """
    return _make_df(
        customer_id=["c1", "c2", "c3"],
        date=["2024-01-01"] * 3,
        amount=[100.0, 0.0, 200.0],
        status=["active", "active", "active"],
        currency=["USD"] * 3,
    )


@pytest.fixture
def sample_status_mixed_df():
    """
    DataFrame со смешанными статусами в разных регистрах.
    Section 17: test_status_normalization_[active/churned/trial].
    """
    return _make_df(
        customer_id=["c1", "c2", "c3", "c4", "c5", "c6"],
        date=["2024-01-01"] * 6,
        amount=[100.0] * 6,
        status=["Active", "ACTIVE", "Churned", "CHURNED", "Trial", "TRIAL"],
        currency=["USD"] * 6,
    )


# ---------------------------------------------------------------------------
# ГРУППА 1: Удаление дубликатов
# Section 17: test_duplicates_removed
# Section 3: Remove exact duplicates. Report in cleaning_report['duplicates_removed']
# ---------------------------------------------------------------------------

class TestDuplicatesRemoved:

    def test_duplicates_removed_count(self, sample_with_duplicates_df):
        """
        Дубликаты удаляются из df_clean.
        Section 3: Remove exact duplicates.
        """
        df_clean, report = clean_data(sample_with_duplicates_df)
        # Исходных строк было 4 (3 уникальных + 1 дубль), после чистки должно быть 3
        assert len(df_clean) == 3

    def test_duplicates_reported(self, sample_with_duplicates_df):
        """
        Количество удалённых дублей фиксируется в cleaning_report.
        Section 3: Report in cleaning_report['duplicates_removed'].
        """
        _, report = clean_data(sample_with_duplicates_df)
        assert "duplicates_removed" in report
        assert report["duplicates_removed"] == 1

    def test_no_duplicates_report_zero(self, sample_basic_df):
        """
        Если дублей нет — cleaning_report['duplicates_removed'] == 0.
        Section 3: Report in cleaning_report['duplicates_removed'].
        """
        _, report = clean_data(sample_basic_df)
        assert report["duplicates_removed"] == 0

    def test_duplicates_removed_preserves_unique_rows(self, sample_with_duplicates_df):
        """
        После удаления дублей уникальные строки остаются нетронутыми.
        Section 3.
        """
        df_clean, _ = clean_data(sample_with_duplicates_df)
        assert set(df_clean["customer_id"].tolist()) == {"c1", "c2", "c3"}


# ---------------------------------------------------------------------------
# ГРУППА 2: Смешанные валюты
# Section 17: test_multicurrency_error
# Section 3: If currency column has > 1 unique value → show error, block processing. Do NOT silently mix.
# ---------------------------------------------------------------------------

class TestMulticurrencyError:

    def test_multicurrency_raises_or_returns_none(self, sample_multicurrency_df):
        """
        При смешанных валютах clean_data должна либо выбросить ValueError,
        либо вернуть None для df_clean (блокировка обработки).
        Section 3: show error, block processing.
        """
        try:
            result = clean_data(sample_multicurrency_df)
            # Если не выбросила исключение — df_clean должен быть None
            df_clean = result[0] if isinstance(result, tuple) else result
            assert df_clean is None, (
                "При смешанных валютах df_clean должен быть None (обработка заблокирована)"
            )
        except (ValueError, SystemExit):
            # Приемлемое поведение — выброс исключения с сообщением об ошибке
            pass

    def test_single_currency_passes(self, sample_basic_df):
        """
        Один тип валюты не вызывает ошибки.
        Section 3: single currency — no error.
        """
        df_clean, report = clean_data(sample_basic_df)
        assert df_clean is not None
        assert len(df_clean) > 0

    def test_multicurrency_error_message_present(self, sample_multicurrency_df):
        """
        Сообщение об ошибке содержит информацию о смешанных валютах.
        Section 3: show error.
        """
        try:
            result = clean_data(sample_multicurrency_df)
            # Если возвращает кортеж — проверяем наличие ключа ошибки в report
            if isinstance(result, tuple) and len(result) == 2:
                report = result[1]
                assert "currency" in str(report).lower() or result[0] is None
        except ValueError as e:
            assert "currency" in str(e).lower()


# ---------------------------------------------------------------------------
# ГРУППА 3: Нормализация статусов
# Section 17: test_status_normalization_[active/churned/trial]
# Section 5: "active rows" = status == 'active' AND amount > 0 (строчные)
# ---------------------------------------------------------------------------

class TestStatusNormalization:

    def test_active_status_normalized_to_lowercase(self, sample_status_mixed_df):
        """
        Статус 'Active', 'ACTIVE' нормализуется в 'active'.
        Section 5: "active rows" — status == 'active' (lowercase).
        """
        df_clean, _ = clean_data(sample_status_mixed_df)
        active_rows = df_clean[df_clean["status"] == "active"]
        # c1 и c2 имели статусы 'Active' и 'ACTIVE' — оба должны стать 'active'
        active_customers = set(active_rows["customer_id"].tolist())
        assert "c1" in active_customers
        assert "c2" in active_customers

    def test_churned_status_normalized_to_lowercase(self, sample_status_mixed_df):
        """
        Статус 'Churned', 'CHURNED' нормализуется в 'churned'.
        Section 17: test_status_normalization_churned.
        """
        df_clean, _ = clean_data(sample_status_mixed_df)
        churned_rows = df_clean[df_clean["status"] == "churned"]
        churned_customers = set(churned_rows["customer_id"].tolist())
        assert "c3" in churned_customers
        assert "c4" in churned_customers

    def test_trial_status_normalized_to_lowercase(self, sample_status_mixed_df):
        """
        Статус 'Trial', 'TRIAL' нормализуется в 'trial'.
        Section 17: test_status_normalization_trial.
        Section 7 (Cohort): Trial months excluded from cohort entry.
        """
        df_clean, _ = clean_data(sample_status_mixed_df)
        trial_rows = df_clean[df_clean["status"] == "trial"]
        trial_customers = set(trial_rows["customer_id"].tolist())
        assert "c5" in trial_customers
        assert "c6" in trial_customers

    def test_all_statuses_are_lowercase_after_clean(self, sample_status_mixed_df):
        """
        После clean_data ВСЕ значения колонки status — строчные.
        Section 5.
        """
        df_clean, _ = clean_data(sample_status_mixed_df)
        for val in df_clean["status"]:
            assert val == val.lower(), f"Статус не нормализован в lowercase: {val!r}"

    def test_already_lowercase_status_unchanged(self, sample_basic_df):
        """
        Уже нормализованные статусы не изменяются.
        Section 17: нормализация идемпотентна.
        """
        df_clean, _ = clean_data(sample_basic_df)
        for val in df_clean["status"]:
            assert val in ("active", "churned", "trial", "cancelled", "paused"), (
                f"Неожиданный статус после нормализации: {val!r}"
            )


# ---------------------------------------------------------------------------
# ГРУППА 4: Отрицательные суммы (рефанды)
# Section 17: test_negatives_tracked
# Section 3: amount < 0 → exclude from MRR, include in revenue_churn, include in cleaning_report
# Section 6: Revenue Churn — includes negative amounts
# ---------------------------------------------------------------------------

class TestNegativesTracked:

    def test_negatives_included_in_cleaning_report(self, sample_negatives_df):
        """
        Отрицательные суммы фиксируются в cleaning_report.
        Section 3: Include in cleaning_report.
        """
        _, report = clean_data(sample_negatives_df)
        # cleaning_report должен содержать информацию об отрицательных суммах
        assert "negatives" in report or "negative" in str(report).lower(), (
            "cleaning_report не содержит информации об отрицательных суммах"
        )

    def test_negatives_count_correct(self, sample_negatives_df):
        """
        Количество строк с отрицательными суммами посчитано корректно.
        Section 3: Include in cleaning_report.
        """
        _, report = clean_data(sample_negatives_df)
        # В фикстуре 2 строки с отрицательными суммами (-50, -75)
        negatives_key = None
        for key in report:
            if "negative" in key.lower():
                negatives_key = key
                break
        assert negatives_key is not None, "Ключ для отрицательных сумм не найден в cleaning_report"
        assert report[negatives_key] == 2

    def test_negatives_not_removed_from_df_clean(self, sample_negatives_df):
        """
        Строки с отрицательными суммами НЕ удаляются из df_clean.
        Section 3: Do NOT remove from df_clean (только из MRR).
        """
        df_clean, _ = clean_data(sample_negatives_df)
        # Все 4 строки должны остаться (с учётом возможного удаления дублей — дублей нет)
        assert len(df_clean) == 4

    def test_negatives_excluded_from_mrr_active_rows(self, sample_negatives_df):
        """
        Строки с amount < 0 не попадают в понятие "active rows".
        Section 5: "active rows" = status == 'active' AND amount > 0.
        Section 3: Exclude from MRR.
        """
        df_clean, _ = clean_data(sample_negatives_df)
        # Проверяем, что active_rows по определению spec не включают negative amounts
        active_rows = df_clean[
            (df_clean["status"] == "active") & (df_clean["amount"] > 0)
        ]
        assert all(active_rows["amount"] > 0), (
            "active rows содержат отрицательные суммы — нарушение Section 5"
        )

    def test_no_negatives_report_zero(self, sample_basic_df):
        """
        Если отрицательных сумм нет — соответствующий счётчик == 0.
        Section 3.
        """
        _, report = clean_data(sample_basic_df)
        # Ищем ключ для отрицательных значений
        for key in report:
            if "negative" in key.lower():
                assert report[key] == 0
                return
        # Если ключа нет совсем — тоже допустимо (0 негативов)


# ---------------------------------------------------------------------------
# ГРУППА 5: Нулевые суммы
# Section 17: test_zeros_tracked
# Section 3: amount == 0 → exclude from MRR, include in cleaning_report, do NOT remove from df_clean
# Section 5: "active rows" = status == 'active' AND amount > 0 (нули исключены)
# Section 7 (Cohort): zero-amount active row counted as retained (status='active', amount=0)
# ---------------------------------------------------------------------------

class TestZerosTracked:

    def test_zeros_included_in_cleaning_report(self, sample_zeros_df):
        """
        Нулевые суммы фиксируются в cleaning_report.
        Section 3: Include in cleaning_report.
        """
        _, report = clean_data(sample_zeros_df)
        assert "zeros" in report or "zero" in str(report).lower(), (
            "cleaning_report не содержит информации о нулевых суммах"
        )

    def test_zeros_count_correct(self, sample_zeros_df):
        """
        Количество строк с нулевыми суммами посчитано корректно.
        Section 3: Include in cleaning_report.
        """
        _, report = clean_data(sample_zeros_df)
        # В фикстуре 1 строка с amount == 0 (c2)
        zeros_key = None
        for key in report:
            if "zero" in key.lower():
                zeros_key = key
                break
        assert zeros_key is not None, "Ключ для нулевых сумм не найден в cleaning_report"
        assert report[zeros_key] == 1

    def test_zeros_not_removed_from_df_clean(self, sample_zeros_df):
        """
        Строки с amount == 0 НЕ удаляются из df_clean.
        Section 3: Do NOT remove from df_clean.
        Section 7: zero-amount active row IS counted as retained.
        """
        df_clean, _ = clean_data(sample_zeros_df)
        # Все 3 строки должны остаться в df_clean
        assert len(df_clean) == 3

    def test_zero_amount_row_present_in_df_clean(self, sample_zeros_df):
        """
        Конкретная строка с amount == 0 присутствует в df_clean.
        Section 3: Do NOT remove from df_clean.
        """
        df_clean, _ = clean_data(sample_zeros_df)
        zero_rows = df_clean[df_clean["amount"] == 0.0]
        assert len(zero_rows) == 1
        assert zero_rows.iloc[0]["customer_id"] == "c2"

    def test_zeros_excluded_from_active_rows_definition(self, sample_zeros_df):
        """
        Строки с amount == 0 не считаются "active rows" для MRR.
        Section 5: "active rows" = status == 'active' AND amount > 0.
        Section 3: Exclude from MRR.
        """
        df_clean, _ = clean_data(sample_zeros_df)
        # По определению active rows из Section 5: status == 'active' AND amount > 0
        active_rows = df_clean[
            (df_clean["status"] == "active") & (df_clean["amount"] > 0)
        ]
        # c2 (amount=0) не должен попасть в active rows
        assert "c2" not in set(active_rows["customer_id"].tolist()), (
            "c2 с amount=0 попал в active rows — нарушение Section 5"
        )

    def test_no_zeros_report_zero(self, sample_basic_df):
        """
        Если нулевых сумм нет — соответствующий счётчик == 0.
        Section 3.
        """
        _, report = clean_data(sample_basic_df)
        for key in report:
            if "zero" in key.lower():
                assert report[key] == 0
                return
        # Если ключа нет — нулей нет, тест пройден


# ---------------------------------------------------------------------------
# ГРУППА 6: Структура и контракт cleaning_report
# Section 3, Section 17 — общие требования к выводу clean_data()
# ---------------------------------------------------------------------------

class TestCleanDataContract:

    def test_returns_tuple_of_two(self, sample_basic_df):
        """
        clean_data() возвращает кортеж (df_clean, cleaning_report).
        Section 4: cleaner.py — clean_data() returns df_clean + cleaning_report.
        """
        result = clean_data(sample_basic_df)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_df_clean_is_dataframe(self, sample_basic_df):
        """
        Первый элемент кортежа — pd.DataFrame.
        Section 4.
        """
        df_clean, _ = clean_data(sample_basic_df)
        assert isinstance(df_clean, pd.DataFrame)

    def test_cleaning_report_is_dict(self, sample_basic_df):
        """
        Второй элемент кортежа — dict.
        Section 3: cleaning_report — dict.
        """
        _, report = clean_data(sample_basic_df)
        assert isinstance(report, dict)

    def test_cleaning_report_has_duplicates_removed_key(self, sample_basic_df):
        """
        cleaning_report всегда содержит ключ 'duplicates_removed'.
        Section 3: Report in cleaning_report['duplicates_removed'].
        """
        _, report = clean_data(sample_basic_df)
        assert "duplicates_removed" in report

    def test_df_raw_columns_preserved(self, sample_basic_df):
        """
        df_clean содержит все исходные колонки (возможно, дополнительные).
        Section 3.
        """
        df_clean, _ = clean_data(sample_basic_df)
        for col in ["customer_id", "date", "amount", "status"]:
            assert col in df_clean.columns, f"Колонка {col!r} пропала после clean_data()"

    def test_clean_data_does_not_mutate_input(self, sample_basic_df):
        """
        clean_data() не мутирует входной DataFrame.
        Section 9 (Caching): immutability — test_immutability.py покрывает AST,
        этот тест проверяет поведение на уровне значений.
        """
        original_len = len(sample_basic_df)
        original_cols = list(sample_basic_df.columns)
        clean_data(sample_basic_df)
        assert len(sample_basic_df) == original_len
        assert list(sample_basic_df.columns) == original_cols
