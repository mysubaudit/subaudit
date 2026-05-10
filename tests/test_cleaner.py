"""
test_cleaner.py — Полный набор тестов для app/core/cleaner.py
Строго по Master Specification Sheet v2.9, Section 17 (Testing — Full Test Matrix)

Тестируемые случаи (Section 17):
  - test_duplicates_removed
  - test_multicurrency_error
  - test_status_normalization_[active/churned/trial]
  - test_negatives_tracked
  - test_zeros_tracked

Дополнительная логика из:
  - Section 3  (Data Limits & Validation)
  - Section 5  (Core Definitions — "active rows" = status == 'active' AND amount > 0)
  - Section 6  (Metric Formulas — amount==0, amount<0 exclusion rules)
  - Section 7  (Cohort — zero-amount active row counted as retained)
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
    Принимает переопределения через kwargs.
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
    Итого 4 строки: 2 положительных, 2 отрицательных.
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
    c2 — единственная строка с amount == 0.
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
        Исходных строк 4 (3 уникальных + 1 дубль) → после чистки должно быть 3.
        """
        df_clean, _ = clean_data(sample_with_duplicates_df)
        assert len(df_clean) == 3

    def test_duplicates_reported(self, sample_with_duplicates_df):
        """
        Количество удалённых дублей фиксируется в cleaning_report['duplicates_removed'].
        Section 3: Report in cleaning_report['duplicates_removed'].
        Ровно 1 дубль добавлен в фикстуре → отчёт должен показать 1.
        """
        _, report = clean_data(sample_with_duplicates_df)
        assert "duplicates_removed" in report, (
            "Ключ 'duplicates_removed' обязателен в cleaning_report (Section 3)"
        )
        assert report["duplicates_removed"] == 1, (
            f"Ожидалось 1 удалённый дубль, получено: {report['duplicates_removed']}"
        )

    def test_no_duplicates_report_zero(self, sample_basic_df):
        """
        Если дублей нет — cleaning_report['duplicates_removed'] == 0.
        Section 3: ключ обязателен всегда, значение 0 при отсутствии дублей.
        """
        _, report = clean_data(sample_basic_df)
        assert "duplicates_removed" in report, (
            "Ключ 'duplicates_removed' обязателен даже при отсутствии дублей"
        )
        assert report["duplicates_removed"] == 0

    def test_duplicates_removed_preserves_unique_rows(self, sample_with_duplicates_df):
        """
        После удаления дублей уникальные строки остаются нетронутыми.
        Section 3: Remove exact duplicates (только дубли, не уникальные).
        """
        df_clean, _ = clean_data(sample_with_duplicates_df)
        assert set(df_clean["customer_id"].tolist()) == {"c1", "c2", "c3"}

    def test_duplicate_is_the_extra_row_not_original(self, sample_with_duplicates_df):
        """
        После удаления дублей остаётся ровно одна строка c1, а не нуль.
        Section 3: Remove exact duplicates — удаляется копия, оригинал остаётся.
        """
        df_clean, _ = clean_data(sample_with_duplicates_df)
        c1_rows = df_clean[df_clean["customer_id"] == "c1"]
        assert len(c1_rows) == 1, (
            "c1 должен присутствовать ровно один раз после удаления дубля"
        )


# ---------------------------------------------------------------------------
# ГРУППА 2: Смешанные валюты
# Section 17: test_multicurrency_error
# Section 3: currency column > 1 unique value → show error, block processing. Do NOT silently mix.
# ---------------------------------------------------------------------------

class TestMulticurrencyError:

    def test_multicurrency_raises_value_error(self, sample_multicurrency_df):
        """
        При смешанных валютах clean_data обязана выбросить ValueError.
        Section 3: show error, block processing — обработка блокируется исключением.
        Только ValueError допустим; SystemExit и тихий возврат None — неприемлемы.
        """
        with pytest.raises(ValueError):
            clean_data(sample_multicurrency_df)

    def test_multicurrency_error_message_mentions_currency(self, sample_multicurrency_df):
        """
        Сообщение ValueError содержит слово 'currency' для информативности.
        Section 3: show error.
        """
        with pytest.raises(ValueError, match=r"(?i)currency"):
            clean_data(sample_multicurrency_df)

    def test_single_currency_passes(self, sample_basic_df):
        """
        Один тип валюты не вызывает ошибки — happy path.
        Section 3: single currency — no error.
        """
        df_clean, report = clean_data(sample_basic_df)
        assert df_clean is not None
        assert len(df_clean) > 0

    def test_two_currencies_both_different_raises(self):
        """
        Два разных значения валюты (не только USD+EUR) — тоже блокируется.
        Section 3: > 1 unique value → error. Правило не зависит от конкретных валют.
        """
        df = _make_df(currency=["GBP", "JPY", "GBP"])
        with pytest.raises(ValueError):
            clean_data(df)


# ---------------------------------------------------------------------------
# ГРУППА 3: Нормализация статусов
# Section 17: test_status_normalization_[active/churned/trial]
# Section 5: "active rows" = status == 'active' AND amount > 0 (lowercase обязателен)
# ---------------------------------------------------------------------------

class TestStatusNormalization:

    def test_active_status_normalized_to_lowercase(self, sample_status_mixed_df):
        """
        Статусы 'Active' и 'ACTIVE' нормализуются в 'active'.
        Section 5: status == 'active' (lowercase).
        Section 17: test_status_normalization_active.
        """
        df_clean, _ = clean_data(sample_status_mixed_df)
        active_rows = df_clean[df_clean["status"] == "active"]
        active_customers = set(active_rows["customer_id"].tolist())
        assert "c1" in active_customers, "c1 (Active) не нормализован в 'active'"
        assert "c2" in active_customers, "c2 (ACTIVE) не нормализован в 'active'"

    def test_churned_status_normalized_to_lowercase(self, sample_status_mixed_df):
        """
        Статусы 'Churned' и 'CHURNED' нормализуются в 'churned'.
        Section 17: test_status_normalization_churned.
        """
        df_clean, _ = clean_data(sample_status_mixed_df)
        churned_rows = df_clean[df_clean["status"] == "churned"]
        churned_customers = set(churned_rows["customer_id"].tolist())
        assert "c3" in churned_customers, "c3 (Churned) не нормализован в 'churned'"
        assert "c4" in churned_customers, "c4 (CHURNED) не нормализован в 'churned'"

    def test_trial_status_normalized_to_lowercase(self, sample_status_mixed_df):
        """
        Статусы 'Trial' и 'TRIAL' нормализуются в 'trial'.
        Section 17: test_status_normalization_trial.
        Section 7 (Cohort): Trial months excluded from cohort entry.
        """
        df_clean, _ = clean_data(sample_status_mixed_df)
        trial_rows = df_clean[df_clean["status"] == "trial"]
        trial_customers = set(trial_rows["customer_id"].tolist())
        assert "c5" in trial_customers, "c5 (Trial) не нормализован в 'trial'"
        assert "c6" in trial_customers, "c6 (TRIAL) не нормализован в 'trial'"

    def test_all_statuses_are_lowercase_after_clean(self, sample_status_mixed_df):
        """
        После clean_data ВСЕ значения колонки status — строчные.
        Section 5: all status comparisons use lowercase.
        """
        df_clean, _ = clean_data(sample_status_mixed_df)
        for val in df_clean["status"]:
            assert val == val.lower(), (
                f"Статус не нормализован в lowercase: {val!r} — нарушение Section 5"
            )

    def test_already_lowercase_status_unchanged(self, sample_basic_df):
        """
        Уже нормализованные статусы ('active') не изменяются.
        Section 17: нормализация идемпотентна.
        Допустимые значения по spec: 'active', 'churned', 'trial' только.
        """
        df_clean, _ = clean_data(sample_basic_df)
        # Только статусы из Section 5 / Section 7 / Section 17
        allowed = {"active", "churned", "trial"}
        for val in df_clean["status"]:
            assert val in allowed, (
                f"Неожиданный статус после нормализации: {val!r} — не предусмотрен spec v2.9"
            )

    def test_normalization_does_not_drop_rows(self, sample_status_mixed_df):
        """
        Нормализация не удаляет строки — только меняет регистр.
        Section 17: нормализация — трансформация, не фильтрация.
        """
        df_clean, _ = clean_data(sample_status_mixed_df)
        assert len(df_clean) == 6, (
            "Нормализация статусов не должна удалять строки"
        )


# ---------------------------------------------------------------------------
# ГРУППА 4: Отрицательные суммы (рефанды)
# Section 17: test_negatives_tracked
# Section 3: amount < 0 → exclude from MRR, include in revenue_churn, include in cleaning_report
# Section 5: "active rows" = status == 'active' AND amount > 0
# ---------------------------------------------------------------------------

class TestNegativesTracked:

    def test_negatives_key_present_in_cleaning_report(self, sample_negatives_df):
        """
        cleaning_report содержит ключ для отрицательных сумм.
        Section 3: Include in cleaning_report.
        Ожидаемое имя ключа: 'negatives_count' (конкретный контракт cleaner.py).
        """
        _, report = clean_data(sample_negatives_df)
        assert "negatives_count" in report, (
            "Ожидается ключ 'negatives_count' в cleaning_report (Section 3)"
        )

    def test_negatives_count_correct(self, sample_negatives_df):
        """
        Количество строк с amount < 0 посчитано корректно.
        Section 3: Include in cleaning_report.
        Фикстура содержит 2 отрицательных строки (c3: -50, c4: -75).
        """
        _, report = clean_data(sample_negatives_df)
        assert report["negatives_count"] == 2, (
            f"Ожидалось 2 отрицательных суммы, получено: {report.get('negatives_count')}"
        )

    def test_negatives_not_removed_from_df_clean(self, sample_negatives_df):
        """
        Строки с amount < 0 НЕ удаляются из df_clean.
        Section 3: Do NOT remove from df_clean (исключаются только из MRR).
        Фикстура — 4 строки без дублей → df_clean должен содержать 4 строки.
        """
        df_clean, _ = clean_data(sample_negatives_df)
        assert len(df_clean) == 4, (
            f"df_clean содержит {len(df_clean)} строк, ожидалось 4 — строки с amount<0 нельзя удалять"
        )

    def test_negative_amounts_present_in_df_clean(self, sample_negatives_df):
        """
        Конкретные строки с отрицательными суммами присутствуют в df_clean.
        Section 3: Do NOT remove from df_clean.
        """
        df_clean, _ = clean_data(sample_negatives_df)
        negative_rows = df_clean[df_clean["amount"] < 0]
        assert len(negative_rows) == 2, (
            "В df_clean должны остаться обе строки с отрицательными суммами"
        )
        negative_customers = set(negative_rows["customer_id"].tolist())
        assert "c3" in negative_customers, "c3 (amount=-50) должен быть в df_clean"
        assert "c4" in negative_customers, "c4 (amount=-75) должен быть в df_clean"

    def test_negatives_excluded_from_active_rows_definition(self, sample_negatives_df):
        """
        Строки с amount < 0 не попадают в "active rows" (MRR-источник).
        Section 5: "active rows" = status == 'active' AND amount > 0.
        Section 3: Exclude from MRR.
        """
        df_clean, _ = clean_data(sample_negatives_df)
        # c4: status='active', amount=-75 — НЕ должен быть в active rows
        active_rows = df_clean[
            (df_clean["status"] == "active") & (df_clean["amount"] > 0)
        ]
        active_customers = set(active_rows["customer_id"].tolist())
        assert "c4" not in active_customers, (
            "c4 (status=active, amount=-75) не должен попасть в active rows — нарушение Section 5"
        )
        # c1 и c2 — должны остаться в active rows
        assert "c1" in active_customers
        assert "c2" in active_customers

    def test_no_negatives_report_zero(self, sample_basic_df):
        """
        Если отрицательных сумм нет — cleaning_report['negatives_count'] == 0.
        Section 3: ключ обязателен всегда, значение 0 при отсутствии негативов.
        """
        _, report = clean_data(sample_basic_df)
        assert "negatives_count" in report, (
            "Ключ 'negatives_count' обязателен даже когда негативов нет"
        )
        assert report["negatives_count"] == 0


# ---------------------------------------------------------------------------
# ГРУППА 5: Нулевые суммы
# Section 17: test_zeros_tracked
# Section 3: amount == 0 → exclude from MRR, include in cleaning_report, do NOT remove from df_clean
# Section 5: "active rows" = status == 'active' AND amount > 0 (нули исключены)
# Section 7 (Cohort): zero-amount active row IS counted as retained (status='active', amount=0)
# ---------------------------------------------------------------------------

class TestZerosTracked:

    def test_zeros_key_present_in_cleaning_report(self, sample_zeros_df):
        """
        cleaning_report содержит ключ для нулевых сумм.
        Section 3: Include in cleaning_report.
        Ожидаемое имя ключа: 'zeros_count' (конкретный контракт cleaner.py).
        """
        _, report = clean_data(sample_zeros_df)
        assert "zeros_count" in report, (
            "Ожидается ключ 'zeros_count' в cleaning_report (Section 3)"
        )

    def test_zeros_count_correct(self, sample_zeros_df):
        """
        Количество строк с amount == 0 посчитано корректно.
        Section 3: Include in cleaning_report.
        Фикстура содержит 1 строку с amount == 0 (c2).
        """
        _, report = clean_data(sample_zeros_df)
        assert report["zeros_count"] == 1, (
            f"Ожидалась 1 нулевая сумма, получено: {report.get('zeros_count')}"
        )

    def test_zeros_not_removed_from_df_clean(self, sample_zeros_df):
        """
        Строки с amount == 0 НЕ удаляются из df_clean.
        Section 3: Do NOT remove from df_clean.
        Section 7: zero-amount active row IS counted as retained.
        Фикстура — 3 строки без дублей → df_clean должен содержать 3 строки.
        """
        df_clean, _ = clean_data(sample_zeros_df)
        assert len(df_clean) == 3, (
            f"df_clean содержит {len(df_clean)} строк, ожидалось 3 — строки с amount=0 нельзя удалять"
        )

    def test_zero_amount_row_present_in_df_clean(self, sample_zeros_df):
        """
        Конкретная строка c2 с amount == 0 присутствует в df_clean.
        Section 3: Do NOT remove from df_clean.
        """
        df_clean, _ = clean_data(sample_zeros_df)
        zero_rows = df_clean[df_clean["amount"] == 0.0]
        assert len(zero_rows) == 1, (
            "В df_clean должна остаться ровно одна строка с amount == 0"
        )
        assert zero_rows.iloc[0]["customer_id"] == "c2", (
            "Строка с amount=0 должна быть c2"
        )

    def test_zeros_excluded_from_active_rows_definition(self, sample_zeros_df):
        """
        Строки с amount == 0 не считаются "active rows" для MRR.
        Section 5: "active rows" = status == 'active' AND amount > 0.
        Section 3: Exclude from MRR.
        c2 (status=active, amount=0) НЕ должен попасть в active rows.
        """
        df_clean, _ = clean_data(sample_zeros_df)
        active_rows = df_clean[
            (df_clean["status"] == "active") & (df_clean["amount"] > 0)
        ]
        assert "c2" not in set(active_rows["customer_id"].tolist()), (
            "c2 с amount=0 попал в active rows — нарушение Section 5"
        )
        # c1 и c3 — должны остаться в active rows
        active_customers = set(active_rows["customer_id"].tolist())
        assert "c1" in active_customers
        assert "c3" in active_customers

    def test_zero_amount_active_counted_as_retained_in_cohort(self, sample_zeros_df):
        """
        Строка с status='active' AND amount=0 считается retained в когортах.
        Section 7 (Cohort): zero-amount active row IS counted as retained.
        Intentional asymmetry: cohort entry requires amount>0, retention only status='active'.
        Тест проверяет, что amount=0 строка остаётся в df_clean и имеет status='active' —
        что позволяет когортному модулю считать её retained.
        """
        df_clean, _ = clean_data(sample_zeros_df)
        zero_active = df_clean[
            (df_clean["customer_id"] == "c2") &
            (df_clean["status"] == "active") &
            (df_clean["amount"] == 0.0)
        ]
        assert len(zero_active) == 1, (
            "c2 (active, amount=0) должен остаться в df_clean для корректного когортного подсчёта"
        )

    def test_no_zeros_report_zero(self, sample_basic_df):
        """
        Если нулевых сумм нет — cleaning_report['zeros_count'] == 0.
        Section 3: ключ обязателен всегда, значение 0 при отсутствии нулей.
        """
        _, report = clean_data(sample_basic_df)
        assert "zeros_count" in report, (
            "Ключ 'zeros_count' обязателен даже когда нулей нет"
        )
        assert report["zeros_count"] == 0


# ---------------------------------------------------------------------------
# ГРУППА 6: Структура и контракт clean_data()
# Section 3, Section 4, Section 17 — общие требования к выводу clean_data()
# ---------------------------------------------------------------------------

class TestCleanDataContract:

    def test_returns_tuple_of_two(self, sample_basic_df):
        """
        clean_data() возвращает кортеж (df_clean, cleaning_report).
        Section 4: cleaner.py — clean_data() returns df_clean + cleaning_report.
        """
        result = clean_data(sample_basic_df)
        assert isinstance(result, tuple), "clean_data() должна вернуть tuple"
        assert len(result) == 2, "Кортеж должен содержать ровно 2 элемента"

    def test_df_clean_is_dataframe(self, sample_basic_df):
        """
        Первый элемент кортежа — pd.DataFrame.
        Section 4: clean_data() returns df_clean.
        """
        df_clean, _ = clean_data(sample_basic_df)
        assert isinstance(df_clean, pd.DataFrame), "df_clean должен быть pd.DataFrame"

    def test_cleaning_report_is_dict(self, sample_basic_df):
        """
        Второй элемент кортежа — dict.
        Section 3: cleaning_report — dict.
        """
        _, report = clean_data(sample_basic_df)
        assert isinstance(report, dict), "cleaning_report должен быть dict"

    def test_cleaning_report_has_duplicates_removed_key(self, sample_basic_df):
        """
        cleaning_report всегда содержит ключ 'duplicates_removed'.
        Section 3: Report in cleaning_report['duplicates_removed'].
        Ключ обязателен даже при отсутствии дублей.
        """
        _, report = clean_data(sample_basic_df)
        assert "duplicates_removed" in report, (
            "Ключ 'duplicates_removed' обязателен в cleaning_report (Section 3)"
        )

    def test_cleaning_report_has_zeros_count_key(self, sample_basic_df):
        """
        cleaning_report всегда содержит ключ 'zeros_count'.
        Section 3: amount == 0 → include in cleaning_report.
        """
        _, report = clean_data(sample_basic_df)
        assert "zeros_count" in report, (
            "Ключ 'zeros_count' обязателен в cleaning_report (Section 3)"
        )

    def test_cleaning_report_has_negatives_count_key(self, sample_basic_df):
        """
        cleaning_report всегда содержит ключ 'negatives_count'.
        Section 3: amount < 0 → include in cleaning_report.
        """
        _, report = clean_data(sample_basic_df)
        assert "negatives_count" in report, (
            "Ключ 'negatives_count' обязателен в cleaning_report (Section 3)"
        )

    def test_df_raw_columns_preserved(self, sample_basic_df):
        """
        df_clean содержит все обязательные исходные колонки.
        Section 3: обязательные колонки для обработки.
        """
        df_clean, _ = clean_data(sample_basic_df)
        for col in ["customer_id", "date", "amount", "status"]:
            assert col in df_clean.columns, (
                f"Обязательная колонка {col!r} пропала после clean_data()"
            )

    def test_clean_data_does_not_mutate_input_shape(self, sample_basic_df):
        """
        clean_data() не мутирует форму входного DataFrame (длину и колонки).
        Section 9 (immutability): df_raw не должен изменяться.
        """
        original_len = len(sample_basic_df)
        original_cols = list(sample_basic_df.columns)
        clean_data(sample_basic_df)
        assert len(sample_basic_df) == original_len, (
            "clean_data() изменила длину входного DataFrame — нарушение иммутабельности"
        )
        assert list(sample_basic_df.columns) == original_cols, (
            "clean_data() изменила колонки входного DataFrame — нарушение иммутабельности"
        )

    def test_clean_data_does_not_mutate_input_values(self, sample_basic_df):
        """
        clean_data() не мутирует значения входного DataFrame.
        Section 9 (immutability): мутация значений (не только формы) тоже запрещена.
        Проверяем конкретные значения amount и status, которые cleaner может изменять.
        """
        original_amounts = sample_basic_df["amount"].copy()
        original_statuses = sample_basic_df["status"].copy()
        clean_data(sample_basic_df)
        pd.testing.assert_series_equal(
            sample_basic_df["amount"], original_amounts,
            check_names=False,
            obj="amount column after clean_data()"
        )
        pd.testing.assert_series_equal(
            sample_basic_df["status"], original_statuses,
            check_names=False,
            obj="status column after clean_data()"
        )
