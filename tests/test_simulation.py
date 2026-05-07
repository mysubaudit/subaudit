"""
tests/test_simulation.py
SubAudit — Master Specification Sheet v2.9
Development Order: Step 8 (Section 16)
Тест-файл для app/core/simulation.py

Тест-матрица (Section 17, test_simulation.py):
  - test_zero_inputs_returns_base_decayed
  - test_churn_reduction_lowers_decay
  - test_mrr_change_pct_none_when_base_zero
  - test_none_guard_no_typeerror
  - test_base_arpu_zero_returns_none        [NEW v2.9 — Section 1, Section 11]
  - test_base_arpu_zero_shows_warning       [NEW v2.9 — Section 1, Section 11]

Фикстуры (Section 17 — Test Fixtures):
  - tests/fixtures/sample_basic.csv         — happy path (500 rows, USD, 12 months)
  - tests/fixtures/sample_zero_arpu.csv     — все active amounts = 0 [NEW v2.9]

ИСПРАВЛЕНИЯ:
  - БАГ 1: антипаттерн try/except TypeError в test_none_guard_no_typeerror
            и test_input_ranges_boundary_values заменён на прямые вызовы.
            pytest автоматически ловит любое неожиданное исключение.
  - БАГ 2: путь мока "streamlit.warning" исправлен на
            "app.core.simulation.st.warning" во всех местах.
  - БАГ 3: размытый assert (result is None or isinstance(result, dict))
            в test_price_increase_negative_allowed заменён на строгий assert dict,
            т.к. df_normal с price_increase=-0.5 — валидные данные, None недопустим.
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Импорт тестируемого модуля
# Section 4: app/core/simulation.py — run_simulation() PRO only
# ---------------------------------------------------------------------------
from app.core.simulation import run_simulation


# ===========================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФАБРИКИ ДАННЫХ
# ===========================================================================

def _make_df(
    n_customers: int = 10,
    n_months: int = 12,
    amount: float = 100.0,
    status: str = "active",
    start_year: int = 2023,
    start_month: int = 1,
) -> pd.DataFrame:
    """
    Генерирует минимальный DataFrame с колонками:
      customer_id, date, amount, status, currency
    Section 5 ("active rows"): status == 'active' AND amount > 0
    """
    rows = []
    for month_offset in range(n_months):
        total_month = start_month + month_offset - 1
        year = start_year + total_month // 12
        month = (total_month % 12) + 1
        for cust_idx in range(1, n_customers + 1):
            rows.append({
                "customer_id": f"cust_{cust_idx:04d}",
                "date": pd.Timestamp(year=year, month=month, day=1),
                "amount": amount,
                "status": status,
                "currency": "USD",
            })
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _make_zero_arpu_df(n_customers: int = 10, n_months: int = 6) -> pd.DataFrame:
    """
    Генерирует DataFrame, где все active rows имеют amount == 0.
    Соответствует фикстуре sample_zero_arpu.csv (Section 17, NEW v2.9).
    Section 11 (base_arpu == 0 guard): должен вернуть None + st.warning().
    """
    return _make_df(
        n_customers=n_customers,
        n_months=n_months,
        amount=0.0,   # все суммы равны нулю
        status="active",
    )


# ===========================================================================
# ФИКСТУРЫ pytest
# ===========================================================================

@pytest.fixture
def df_normal():
    """
    Стандартный DataFrame: 10 клиентов, 12 месяцев, amount=100 USD.
    Соответствует sample_basic.csv (Section 17).
    MRR_last = 10 * 100 = 1000, ARPU = 100.
    """
    return _make_df(n_customers=10, n_months=12, amount=100.0)


@pytest.fixture
def df_zero_arpu():
    """
    DataFrame, где все active amount == 0.
    Соответствует sample_zero_arpu.csv (Section 17, NEW v2.9).
    Ожидаем: run_simulation() → None + st.warning() (Section 11).
    """
    return _make_zero_arpu_df(n_customers=10, n_months=6)


@pytest.fixture
def df_zero_mrr():
    """
    DataFrame без активных строк — base_mrr == 0.
    Section 11: mrr_change_pct = None (не делить на ноль).
    """
    return _make_df(
        n_customers=5,
        n_months=3,
        amount=50.0,
        status="churned",  # нет active rows → MRR = 0
    )


# ===========================================================================
# ТЕСТЫ
# ===========================================================================

class TestSimulationBasicBehaviour:
    """
    Базовое поведение run_simulation() при нормальных входных данных.
    Section 11 — Input Parameters, когортная формула затухания MRR.
    """

    def test_zero_inputs_returns_base_decayed(self, df_normal):
        """
        Section 17: test_zero_inputs_returns_base_decayed
        При нулевых входных параметрах симуляция возвращает базовое затухание MRR.
        Результат не должен быть None — данные валидны.
        """
        result = run_simulation(
            df=df_normal,
            churn_reduction=0.0,
            new_customers_month=0,
            price_increase=0.0,
        )
        assert result is not None, (
            "run_simulation() не должен возвращать None при валидных входных данных "
            "(Section 11)"
        )
        assert isinstance(result, dict), (
            "run_simulation() должен возвращать dict (Section 11)"
        )
        assert "monthly_mrr" in result, "Ожидается ключ 'monthly_mrr' в результате"
        assert "mrr_change_pct" in result, "Ожидается ключ 'mrr_change_pct' в результате"

    def test_zero_inputs_mrr_is_non_negative(self, df_normal):
        """
        Section 11: все значения monthly_mrr >= 0.
        """
        result = run_simulation(
            df=df_normal,
            churn_reduction=0.0,
            new_customers_month=0,
            price_increase=0.0,
        )
        assert result is not None
        assert all(v >= 0 for v in result["monthly_mrr"]), (
            "Все значения monthly_mrr должны быть >= 0 (Section 11)"
        )

    def test_churn_reduction_lowers_decay(self, df_normal):
        """
        Section 17: test_churn_reduction_lowers_decay
        При churn_reduction > 0 итоговый MRR через 12 месяцев должен быть
        ВЫШЕ, чем при churn_reduction == 0, при прочих равных.
        Section 11: new_churn_rate = churn_rate * (1 - churn_reduction).
        """
        result_no_reduction = run_simulation(
            df=df_normal,
            churn_reduction=0.0,
            new_customers_month=0,
            price_increase=0.0,
        )
        result_with_reduction = run_simulation(
            df=df_normal,
            churn_reduction=0.5,  # 50% снижение оттока
            new_customers_month=0,
            price_increase=0.0,
        )
        assert result_no_reduction is not None
        assert result_with_reduction is not None
        assert result_with_reduction["monthly_mrr"][-1] >= result_no_reduction["monthly_mrr"][-1], (
            "Снижение churn_reduction должно замедлять затухание MRR (Section 11)"
        )

    def test_churn_reduction_full_stops_decay(self, df_normal):
        """
        Section 11: При churn_reduction=1.0 → new_churn_rate=0.0 →
        base MRR остаётся константным (без новых клиентов и без изменения цены).
        """
        result = run_simulation(
            df=df_normal,
            churn_reduction=1.0,
            new_customers_month=0,
            price_increase=0.0,
        )
        assert result is not None
        monthly = result["monthly_mrr"]
        first_val = monthly[0]
        for i, val in enumerate(monthly):
            assert abs(val - first_val) < 0.01, (
                f"При churn_reduction=1.0 MRR должен оставаться константным, "
                f"но month {i} = {val} != {first_val} (Section 11)"
            )

    def test_new_customers_increases_mrr(self, df_normal):
        """
        Section 11: new_customers_month > 0 добавляет новых клиентов →
        итоговый MRR должен быть выше, чем без новых клиентов.
        """
        result_no_new = run_simulation(
            df=df_normal,
            churn_reduction=0.0,
            new_customers_month=0,
            price_increase=0.0,
        )
        result_with_new = run_simulation(
            df=df_normal,
            churn_reduction=0.0,
            new_customers_month=5,
            price_increase=0.0,
        )
        assert result_no_new is not None
        assert result_with_new is not None
        assert result_with_new["monthly_mrr"][-1] > result_no_new["monthly_mrr"][-1], (
            "Добавление new_customers_month должно увеличивать итоговый MRR (Section 11)"
        )

    def test_price_increase_increases_mrr(self, df_normal):
        """
        Section 11: price_increase > 0 → new_arpu = base_arpu * (1 + price_increase)
        → MRR с ценовым ростом выше, чем без него.
        """
        result_no_price = run_simulation(
            df=df_normal,
            churn_reduction=0.0,
            new_customers_month=0,
            price_increase=0.0,
        )
        result_with_price = run_simulation(
            df=df_normal,
            churn_reduction=0.0,
            new_customers_month=0,
            price_increase=0.1,  # +10% к ARPU
        )
        assert result_no_price is not None
        assert result_with_price is not None
        assert result_with_price["monthly_mrr"][0] > result_no_price["monthly_mrr"][0], (
            "Ценовой рост должен увеличивать стартовый MRR симуляции (Section 11)"
        )


class TestSimulationEdgeCases:
    """
    Граничные случаи: base_mrr == 0, base_arpu == 0, None-guard.
    Section 11 — base_arpu == 0 Guard (NEW v2.9), Section 1 Changelog.
    """

    def test_mrr_change_pct_none_when_base_zero(self, df_zero_mrr):
        """
        Section 17: test_mrr_change_pct_none_when_base_zero
        Section 11: если base_mrr == 0 → mrr_change_pct = None.
        Нельзя делить на ноль — результат должен содержать None, а не падать.
        """
        result = run_simulation(
            df=df_zero_mrr,
            churn_reduction=0.0,
            new_customers_month=0,
            price_increase=0.0,
        )
        if result is not None:
            assert result.get("mrr_change_pct") is None, (
                "mrr_change_pct должен быть None при base_mrr == 0 (Section 11)"
            )
        # Если result сам None — тест тоже проходит: функция корректно отказала

    def test_none_guard_no_typeerror(self, df_zero_mrr):
        """
        Section 17: test_none_guard_no_typeerror
        При любых входных данных run_simulation() не должен бросать TypeError.
        Допустимы только None или dict в качестве возврата.

        БАГ 1 ИСПРАВЛЕН: убран антипаттерн try/except TypeError.
        pytest автоматически фиксирует любое исключение — включая TypeError.
        """
        # БАГ 1 ИСПРАВЛЕН: прямой вызов без try/except
        result = run_simulation(
            df=df_zero_mrr,
            churn_reduction=0.0,
            new_customers_month=0,
            price_increase=0.0,
        )
        assert result is None or isinstance(result, dict), (
            "run_simulation() должен возвращать None или dict (Section 11)"
        )

    def test_simulation_horizon_12_months(self, df_normal):
        """
        Section 11: горизонт симуляции — 12 месяцев вперёд.
        monthly_mrr должен содержать ровно 12 элементов.
        """
        result = run_simulation(
            df=df_normal,
            churn_reduction=0.0,
            new_customers_month=0,
            price_increase=0.0,
        )
        assert result is not None
        assert len(result["monthly_mrr"]) == 12, (
            "Горизонт симуляции должен быть 12 месяцев (Section 11)"
        )

    def test_input_ranges_boundary_values(self, df_normal):
        """
        Section 11 — Input Parameters: граничные значения диапазонов.
          churn_reduction: 0.0–1.0
          new_customers_month: 0–10,000
          price_increase: -0.5–5.0
        Проверяем, что граничные значения не вызывают исключений.

        БАГ 1 ИСПРАВЛЕН: убран антипаттерн try/except Exception.
        pytest автоматически фиксирует любое неожиданное исключение.
        """
        boundary_cases = [
            # (churn_reduction, new_customers_month, price_increase)
            (0.0, 0, -0.5),
            (1.0, 10_000, 5.0),
            (0.5, 100, 0.0),
        ]
        for cr, ncm, pi in boundary_cases:
            # БАГ 1 ИСПРАВЛЕН: прямой вызов без try/except
            result = run_simulation(
                df=df_normal,
                churn_reduction=cr,
                new_customers_month=ncm,
                price_increase=pi,
            )
            assert result is None or isinstance(result, dict), (
                f"run_simulation() вернул неожиданный тип при "
                f"churn_reduction={cr}, new_customers_month={ncm}, "
                f"price_increase={pi} — ожидался None или dict (Section 11)"
            )


# ===========================================================================
# ТЕСТЫ v2.9 — base_arpu == 0 Guard (NEW)
# Section 1 Changelog: "FIXED — Simulation base_arpu == 0 guard"
# Section 11: "base_arpu == 0 Guard (NEW in v2.9)"
# Section 17: test_base_arpu_zero_returns_none, test_base_arpu_zero_shows_warning
# ===========================================================================

# Точный текст предупреждения из Section 11 — не менять
_EXPECTED_ARPU_WARNING = (
    "ARPU is zero — price increase cannot be modelled. "
    "Upload data with non-zero active amounts."
)


class TestBaseArpuZeroGuard:
    """
    Тесты для guard-условия base_arpu == 0, добавленного в v2.9.

    Section 1 (Changelog):
        "Added explicit guard in run_simulation(): if base_arpu == 0,
         return None and show st.warning(...).
         Previously: new_arpu = 0 * (1 + price_increase) = 0 silently,
         producing wrong results."

    Section 11 (base_arpu == 0 Guard):
        - Return None immediately.
        - Show st.warning("ARPU is zero — price increase cannot be modelled.
          Upload data with non-zero active amounts.")
        - Do NOT proceed with simulation.

    Фикстура: sample_zero_arpu.csv (Section 17) — все active amounts = 0.
    """

    def test_base_arpu_zero_returns_none(self, df_zero_arpu):
        """
        Section 17 [NEW v2.9]: test_base_arpu_zero_returns_none
        Когда все active amount == 0, ARPU == 0 → run_simulation() → None.
        Section 11, Section 1 Changelog.
        """
        # Заглушаем st.warning — он вызывается как побочный эффект guard
        # БАГ 2 ИСПРАВЛЕН: полный путь мока
        with patch("app.core.simulation.st.warning"):
            result = run_simulation(
                df=df_zero_arpu,
                churn_reduction=0.0,
                new_customers_month=0,
                price_increase=0.0,
            )
        assert result is None, (
            "run_simulation() должен вернуть None при base_arpu == 0 "
            "(Section 11, Section 1 v2.9 Changelog)"
        )

    def test_base_arpu_zero_returns_none_with_price_increase(self, df_zero_arpu):
        """
        Даже при price_increase > 0 guard должен сработать до умножения.
        Section 11 — "return None immediately".
        Было: new_arpu = 0 * (1 + price_increase) = 0 → тихо неверный результат.
        Стало: guard возвращает None до любых вычислений.
        """
        # БАГ 2 ИСПРАВЛЕН: полный путь мока
        with patch("app.core.simulation.st.warning"):
            result = run_simulation(
                df=df_zero_arpu,
                churn_reduction=0.0,
                new_customers_month=5,
                price_increase=0.5,  # должно быть проигнорировано guard-ом
            )
        assert result is None, (
            "При base_arpu == 0 guard должен сработать ДО умножения на price_increase "
            "(Section 11)"
        )

    def test_base_arpu_zero_shows_warning(self, df_zero_arpu):
        """
        Section 17 [NEW v2.9]: test_base_arpu_zero_shows_warning
        При base_arpu == 0 функция должна вызвать st.warning() с точным текстом
        из Section 11.

        БАГ 2 ИСПРАВЛЕН: patch("app.core.simulation.st.warning")
        вместо patch("streamlit.warning").
        """
        # БАГ 2 ИСПРАВЛЕН: полный путь мока
        with patch("app.core.simulation.st.warning") as mock_warning:
            result = run_simulation(
                df=df_zero_arpu,
                churn_reduction=0.0,
                new_customers_month=0,
                price_increase=0.0,
            )

        assert result is None, (
            "run_simulation() должен вернуть None при base_arpu == 0 (Section 11)"
        )

        assert mock_warning.called, (
            "st.warning() должен быть вызван при base_arpu == 0 (Section 11)"
        )

        # Проверяем точный текст предупреждения (Section 11 — verbatim)
        all_warning_args = [
            str(c.args[0]) if c.args else str(c.kwargs.get("body", ""))
            for c in mock_warning.call_args_list
        ]
        assert any(_EXPECTED_ARPU_WARNING in arg for arg in all_warning_args), (
            f"st.warning() должен быть вызван с текстом:\n  '{_EXPECTED_ARPU_WARNING}'\n"
            f"Фактические вызовы:\n  {all_warning_args}\n"
            f"(Section 11 — verbatim warning text)"
        )

    def test_base_arpu_zero_does_not_proceed(self, df_zero_arpu):
        """
        Section 11: "Do NOT proceed with simulation."
        При base_arpu == 0 функция возвращает None немедленно.
        """
        # БАГ 2 ИСПРАВЛЕН: полный путь мока
        with patch("app.core.simulation.st.warning"):
            result = run_simulation(
                df=df_zero_arpu,
                churn_reduction=0.5,
                new_customers_month=100,
                price_increase=1.0,
            )
        assert result is None, (
            "run_simulation() должен немедленно вернуть None без продолжения "
            "вычислений при base_arpu == 0 (Section 11)"
        )


# ===========================================================================
# ТЕСТЫ ПАРАМЕТРОВ СИМУЛЯЦИИ — детальные проверки формул
# Section 11 — Input Parameters, формула когортного затухания
# ===========================================================================

class TestSimulationParameters:
    """
    Проверка корректности входных параметров (диапазоны, типы).
    Section 11 — Input Parameters table.
    """

    def test_churn_reduction_range_lower_bound(self, df_normal):
        """
        Section 11: churn_reduction ∈ [0.0, 1.0].
        Нижняя граница 0.0 — без изменений оттока.
        """
        result = run_simulation(
            df=df_normal,
            churn_reduction=0.0,
            new_customers_month=0,
            price_increase=0.0,
        )
        assert result is not None

    def test_churn_reduction_range_upper_bound(self, df_normal):
        """
        Section 11: churn_reduction = 1.0 → отток полностью устранён.
        """
        result = run_simulation(
            df=df_normal,
            churn_reduction=1.0,
            new_customers_month=0,
            price_increase=0.0,
        )
        assert result is not None

    def test_price_increase_negative_allowed(self, df_normal):
        """
        Section 11: price_increase ∈ [-0.5, 5.0].
        Отрицательное значение (-0.5) означает снижение цены — допустимо.

        БАГ 3 ИСПРАВЛЕН: при df_normal (валидные данные, ARPU > 0)
        и допустимом price_increase=-0.5 функция должна вернуть dict, не None.
        Размытый assert (None or dict) заменён на строгий assert isinstance(result, dict).
        """
        result = run_simulation(
            df=df_normal,
            churn_reduction=0.0,
            new_customers_month=0,
            price_increase=-0.5,
        )
        # БАГ 3 ИСПРАВЛЕН: df_normal имеет ARPU > 0, guard не срабатывает
        assert isinstance(result, dict), (
            "При валидных данных и допустимом price_increase=-0.5 "
            "run_simulation() должен вернуть dict (Section 11)"
        )

    def test_new_customers_upper_bound(self, df_normal):
        """
        Section 11: new_customers_month ∈ [0, 10_000].
        Максимальное значение 10_000 не должно вызывать ошибку.
        """
        result = run_simulation(
            df=df_normal,
            churn_reduction=0.0,
            new_customers_month=10_000,
            price_increase=0.0,
        )
        assert isinstance(result, dict), (
            "При new_customers_month=10_000 run_simulation() должен вернуть dict "
            "(Section 11)"
        )

    def test_result_dict_contains_required_keys(self, df_normal):
        """
        Результат симуляции должен содержать ключи для Dashboard PRO.
        Section 2: Simulation — PRO only: "Dashboard + PDF export".
        Section 11: mrr_change_pct = None при base_mrr == 0.
        """
        result = run_simulation(
            df=df_normal,
            churn_reduction=0.1,
            new_customers_month=2,
            price_increase=0.05,
        )
        assert result is not None
        required_keys = {"monthly_mrr", "mrr_change_pct"}
        missing = required_keys - set(result.keys())
        assert not missing, (
            f"В результате симуляции отсутствуют ключи: {missing} (Section 11)"
        )


# ===========================================================================
# ИНТЕГРАЦИОННЫЙ ТЕСТ С ФАЙЛОВОЙ ФИКСТУРОЙ
# Section 17 — Test Fixtures: sample_zero_arpu.csv
# ===========================================================================

class TestSimulationWithFileFixtures:
    """
    Интеграционные тесты с CSV-фикстурами из tests/fixtures/.
    Section 17 — Test Fixtures.
    Тесты пропускаются (pytest.skip), если файл фикстуры ещё не создан.
    """

    @pytest.fixture
    def sample_zero_arpu_from_file(self):
        """
        Загружает фикстуру sample_zero_arpu.csv (Section 17, NEW v2.9).
        Все active amounts = 0 — triggers base_arpu==0 guard in simulation.
        """
        fixture_path = "tests/fixtures/sample_zero_arpu.csv"
        try:
            return pd.read_csv(fixture_path, parse_dates=["date"])
        except FileNotFoundError:
            pytest.skip(
                f"Фикстура {fixture_path} не найдена. "
                f"Создайте её согласно Section 17 перед запуском теста."
            )

    @pytest.fixture
    def sample_basic_from_file(self):
        """
        Загружает фикстуру sample_basic.csv (Section 17).
        500 rows, USD, 12 months, clean — happy path.
        """
        fixture_path = "tests/fixtures/sample_basic.csv"
        try:
            return pd.read_csv(fixture_path, parse_dates=["date"])
        except FileNotFoundError:
            pytest.skip(
                f"Фикстура {fixture_path} не найдена. "
                f"Создайте её согласно Section 17 перед запуском теста."
            )

    def test_file_fixture_zero_arpu_returns_none(self, sample_zero_arpu_from_file):
        """
        Интеграционный тест: sample_zero_arpu.csv → run_simulation() → None.
        Section 17 (NEW v2.9): sample_zero_arpu.csv — triggers base_arpu==0 guard.
        """
        # БАГ 2 ИСПРАВЛЕН: полный путь мока
        with patch("app.core.simulation.st.warning"):
            result = run_simulation(
                df=sample_zero_arpu_from_file,
                churn_reduction=0.0,
                new_customers_month=0,
                price_increase=0.0,
            )
        assert result is None, (
            "sample_zero_arpu.csv должен привести к None из run_simulation() "
            "(Section 11, Section 17)"
        )

    def test_file_fixture_basic_returns_dict(self, sample_basic_from_file):
        """
        Интеграционный тест: sample_basic.csv → run_simulation() → dict.
        Section 17: sample_basic.csv — 500 rows, USD, 12 months, clean (happy path).
        """
        result = run_simulation(
            df=sample_basic_from_file,
            churn_reduction=0.1,
            new_customers_month=5,
            price_increase=0.05,
        )
        assert result is not None, (
            "sample_basic.csv должен успешно проходить симуляцию (Section 17)"
        )
        assert isinstance(result, dict)
