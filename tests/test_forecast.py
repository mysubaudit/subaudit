"""
test_forecast.py — Полный набор тестов для app/core/forecast.py
Соответствует: SubAudit Master Specification Sheet v2.9
Раздел: Section 17 (Testing — Full Test Matrix), Section 10 (Forecast)
Development Order: Step 8
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock
from datetime import date
from dateutil.relativedelta import relativedelta


# ---------------------------------------------------------------------------
# Вспомогательные фабрики для генерации тестовых DataFrame
# Section 5 (Core Definitions): "active rows" = status == 'active' AND amount > 0
# ---------------------------------------------------------------------------

def _make_months(n: int, base: date | None = None) -> list[str]:
    """Генерирует список из n месяцев в формате YYYY-MM-01, начиная с base."""
    if base is None:
        base = date(2023, 1, 1)
    return [(base + relativedelta(months=i)).strftime("%Y-%m-01") for i in range(n)]


def _build_df(months: list[str], mrr_per_month: list[float]) -> pd.DataFrame:
    """
    Создаёт DataFrame с активными подписчиками для каждого месяца.
    Один клиент на месяц с заданным amount — минимальная структура для forecast.
    """
    rows = []
    for i, (month, amount) in enumerate(zip(months, mrr_per_month)):
        rows.append({
            "customer_id": f"cust_{i:03d}",
            "date": month,
            "status": "active",
            "amount": amount,
            "currency": "USD",
        })
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _load_fixture(filename: str) -> pd.DataFrame:
    """
    Загружает CSV-фикстуру из tests/fixtures/.
    Section 17: fixtures используются для специфических сценариев.
    """
    import os
    path = os.path.join(os.path.dirname(__file__), "fixtures", filename)
    df = pd.read_csv(path)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


# ---------------------------------------------------------------------------
# Fixtures — pytest
# ---------------------------------------------------------------------------

@pytest.fixture
def df_sparse():
    """
    2 месяца данных — меньше минимального порога 3 месяцев.
    Section 10: < 3 months data → return None.
    Соответствует: tests/fixtures/sample_sparse.csv (Section 17).
    """
    months = _make_months(2)
    return _build_df(months, [1000.0, 1100.0])


@pytest.fixture
def df_3mo():
    """
    3 месяца данных — граничный случай без сезонности.
    Section 10: 3–5 months → HoltWinters WITHOUT seasonal. Realistic only.
    """
    months = _make_months(3)
    return _build_df(months, [1000.0, 1100.0, 1200.0])


@pytest.fixture
def df_5mo():
    """
    5 месяцев данных — верхняя граница режима без сезонности.
    Section 10: 3–5 months → Realistic scenario ONLY. Show st.warning() BEFORE chart.
    """
    months = _make_months(5)
    return _build_df(months, [1000.0, 1100.0, 1050.0, 1200.0, 1150.0])


@pytest.fixture
def df_6mo():
    """
    6 месяцев данных — минимум для всех трёх сценариев.
    Section 10: ≥ 6 months → HoltWinters with trend + seasonal. All 3 scenarios. Export enabled.
    """
    months = _make_months(6)
    return _build_df(months, [1000.0, 1100.0, 1050.0, 1200.0, 1150.0, 1300.0])


@pytest.fixture
def df_12mo():
    """
    12 месяцев данных — стандартный happy path.
    Section 17: tests/fixtures/sample_basic.csv — 500 rows, 12 months.
    """
    months = _make_months(12)
    mrr = [1000 + i * 50 for i in range(12)]
    return _build_df(months, mrr)


@pytest.fixture
def df_degenerate():
    """
    Идентичные значения MRR — вызывает HoltWinters ValueError.
    Section 10 / Section 17: sample_degenerate_forecast.csv.
    Section 1 (Changelog v2.9): HoltWinters exception handling — FIXED.
    """
    months = _make_months(6)
    # Все значения одинаковые — вырожденный паттерн
    return _build_df(months, [1000.0] * 6)


# ---------------------------------------------------------------------------
# Импорт тестируемого модуля
# Section 4: app/core/forecast.py
# ---------------------------------------------------------------------------

# Используем отложенный импорт чтобы моки работали корректно
from app.core.forecast import generate_forecast  # noqa: E402


# ===========================================================================
# БЛОК 1: Тесты граничных условий по количеству месяцев
# Section 10: правила по диапазонам данных
# ===========================================================================

class TestReturnNoneSparse:
    """
    test_returns_none_sparse — Section 17, Section 10.
    < 3 месяцев данных → return None.
    """

    def test_returns_none_sparse(self, df_sparse):
        """
        Если данных меньше 3 месяцев — функция обязана вернуть None.
        Section 10: "< 3 months data → Return None."
        """
        result = generate_forecast(df_sparse)
        assert result is None, (
            "generate_forecast должна вернуть None при < 3 месяцах данных "
            "(Section 10)"
        )

    def test_shows_info_message_sparse(self, df_sparse):
        """
        При < 3 месяцах данных должно отображаться st.info с конкретным текстом.
        Section 10: 'At least 3 months of data are required to generate a forecast.'
        """
        with patch("app.core.forecast.st") as mock_st:
            generate_forecast(df_sparse)
            # Проверяем что st.info был вызван с нужным сообщением
            mock_st.info.assert_called_once_with(
                "At least 3 months of data are required to generate a forecast."
            )


# ===========================================================================
# БЛОК 2: Сценарии при 3–5 месяцах данных
# Section 10: HoltWinters WITHOUT seasonal; Realistic scenario ONLY;
#             Show st.warning() BEFORE chart; Export blocked.
# ===========================================================================

class TestThreeToFiveMonths:
    """
    Тесты для диапазона 3–5 месяцев данных.
    Section 10: "3–5 months data → HoltWinters WITHOUT seasonal. Realistic scenario ONLY."
    """

    def test_only_realistic_scenario_at_3mo(self, df_3mo):
        """
        При 3 месяцах данных возвращается только реалистичный сценарий.
        Section 10: Realistic scenario ONLY при 3–5 months.
        """
        result = generate_forecast(df_3mo)
        # Если вернулось не None — проверяем отсутствие pessimistic/optimistic
        if result is not None:
            assert "pessimistic" not in result, (
                "Пессимистичный сценарий недоступен при < 6 месяцах данных "
                "(Section 10)"
            )
            assert "optimistic" not in result, (
                "Оптимистичный сценарий недоступен при < 6 месяцах данных "
                "(Section 10)"
            )
            assert "realistic" in result, (
                "Реалистичный сценарий должен присутствовать при 3–5 месяцах "
                "(Section 10)"
            )

    def test_warning_rendered_before_chart_3_5mo(self, df_5mo):
        """
        st.warning() ОБЯЗАН быть вызван ДО рендеринга чарта при 3–5 месяцах.
        Section 10: "Show st.warning() BEFORE chart."
        Section 17: test_warning_rendered_before_chart_3_5mo.
        """
        call_order = []

        with patch("app.core.forecast.st") as mock_st:
            mock_st.warning.side_effect = lambda msg: call_order.append("warning")
            # Имитируем вызов chart через любой plotly/st.plotly_chart
            mock_st.plotly_chart = MagicMock(
                side_effect=lambda *a, **kw: call_order.append("chart")
            )
            generate_forecast(df_5mo)

        if "chart" in call_order and "warning" in call_order:
            warning_idx = call_order.index("warning")
            chart_idx = call_order.index("chart")
            assert warning_idx < chart_idx, (
                "st.warning() должен вызываться ДО рендеринга чарта "
                "(Section 10)"
            )

    def test_export_gate_blocks_under_6mo(self, df_5mo):
        """
        При data_months_used < 6 экспорт должен быть заблокирован.
        Section 10: "Export gate: forecast_dict = None when data_months_used < 6."
        Section 17: test_export_gate_blocks_under_6mo.
        """
        result = generate_forecast(df_5mo)
        # forecast_dict должен быть None ИЛИ содержать маркер экспортного блока
        if result is not None:
            # Если возвращается dict — поле экспорта должно указывать на блокировку
            export_ready = result.get("export_ready", False)
            assert export_ready is False, (
                "Экспорт должен быть заблокирован при data_months_used < 6 "
                "(Section 10)"
            )


# ===========================================================================
# БЛОК 3: Сценарии при ≥ 6 месяцах данных
# Section 10: "≥ 6 months → HoltWinters with trend + seasonal. All 3 scenarios."
# ===========================================================================

class TestSixPlusMonths:
    """
    Тесты для ≥ 6 месяцев данных — полный режим прогноза.
    """

    def test_scenarios_enabled_at_6mo(self, df_6mo):
        """
        При ≥ 6 месяцах все три сценария должны быть доступны.
        Section 10: "All 3 scenarios."
        Section 17: test_scenarios_enabled_at_6mo.
        """
        result = generate_forecast(df_6mo)
        assert result is not None, (
            "generate_forecast не должна возвращать None при 6+ месяцах данных "
            "(Section 10)"
        )
        assert "realistic" in result, "Отсутствует реалистичный сценарий (Section 10)"
        assert "pessimistic" in result, "Отсутствует пессимистичный сценарий (Section 10)"
        assert "optimistic" in result, "Отсутствует оптимистичный сценарий (Section 10)"

    def test_horizon_is_12_months(self, df_12mo):
        """
        Горизонт прогноза — ровно 12 месяцев вперёд.
        Section 10: "Horizon: 12 months forward."
        """
        result = generate_forecast(df_12mo)
        assert result is not None
        realistic = result.get("realistic", [])
        assert len(realistic) == 12, (
            f"Горизонт прогноза должен быть 12 месяцев, получено {len(realistic)} "
            "(Section 10)"
        )

    def test_export_enabled_at_6mo(self, df_6mo):
        """
        При ≥ 6 месяцах экспорт должен быть разрешён.
        Section 10: "Export enabled" при ≥ 6 months.
        """
        result = generate_forecast(df_6mo)
        assert result is not None
        export_ready = result.get("export_ready", True)
        assert export_ready is True, (
            "Экспорт должен быть разрешён при ≥ 6 месяцах данных (Section 10)"
        )

    def test_pessimistic_formula(self, df_12mo):
        """
        Пессимистичный сценарий: projected × (1 − churn_rate/100 × 1.20).
        Section 10: "Pessimistic (≥ 6mo): projected × (1 − churn_rate/100 × 1.20)"
        """
        result = generate_forecast(df_12mo)
        assert result is not None
        realistic = result.get("realistic", [])
        pessimistic = result.get("pessimistic", [])
        churn_rate = result.get("churn_rate_used", 0.05)

        for r, p in zip(realistic, pessimistic):
            expected = r * (1 - churn_rate / 100 * 1.20)
            expected = max(expected, 0)  # negative guard — Section 10
            assert abs(p - expected) < 0.01, (
                f"Пессимистичный сценарий неверен: ожидалось {expected:.4f}, "
                f"получено {p:.4f} (Section 10)"
            )

    def test_optimistic_formula(self, df_12mo):
        """
        Оптимистичный сценарий: projected × (1 − churn_rate/100 × 0.80).
        Section 10: "Optimistic (≥ 6mo): projected × (1 − churn_rate/100 × 0.80)"
        """
        result = generate_forecast(df_12mo)
        assert result is not None
        realistic = result.get("realistic", [])
        optimistic = result.get("optimistic", [])
        churn_rate = result.get("churn_rate_used", 0.05)

        for r, o in zip(realistic, optimistic):
            expected = r * (1 - churn_rate / 100 * 0.80)
            expected = max(expected, 0)  # negative guard — Section 10
            assert abs(o - expected) < 0.01, (
                f"Оптимистичный сценарий неверен: ожидалось {expected:.4f}, "
                f"получено {o:.4f} (Section 10)"
            )

    def test_realistic_is_projected_as_is(self, df_12mo):
        """
        Реалистичный сценарий — прогноз без модификаций.
        Section 10: "Realistic: projected as-is."
        """
        result = generate_forecast(df_12mo)
        assert result is not None
        # Realistic не должен быть None или пустым
        realistic = result.get("realistic", [])
        assert len(realistic) > 0, (
            "Реалистичный сценарий не должен быть пустым (Section 10)"
        )


# ===========================================================================
# БЛОК 4: Negative guard — все значения yhat >= 0
# Section 10: "Negative guard: Clamp all yhat to >= 0"
# ===========================================================================

class TestNoNegativeYhat:
    """
    test_no_negative_yhat — Section 17, Section 10.
    """

    def test_no_negative_yhat(self, df_12mo):
        """
        Все значения прогноза должны быть >= 0.
        Section 10: "Negative guard: Clamp all yhat to >= 0."
        Section 17: test_no_negative_yhat.
        """
        result = generate_forecast(df_12mo)
        assert result is not None

        for scenario in ("realistic", "pessimistic", "optimistic"):
            values = result.get(scenario, [])
            for i, v in enumerate(values):
                assert v >= 0, (
                    f"Отрицательное значение yhat в сценарии '{scenario}' "
                    f"на позиции {i}: {v}. Negative guard нарушен (Section 10)"
                )

    def test_no_negative_yhat_sparse_data(self, df_6mo):
        """
        Negative guard работает также при минимальном наборе данных (6 мес).
        """
        result = generate_forecast(df_6mo)
        if result is not None:
            for scenario in ("realistic", "pessimistic", "optimistic"):
                for v in result.get(scenario, []):
                    assert v >= 0, (
                        f"Negative guard нарушен при 6 месяцах данных "
                        f"(Section 10)"
                    )


# ===========================================================================
# БЛОК 5: Churn fallback = 0.05 когда churn_rate is None
# Section 10: "Churn fallback: churn_rate is None → use 0.05"
# ===========================================================================

class TestChurnFallback:
    """
    Тесты fallback значения churn_rate.
    """

    def test_churn_fallback_when_none(self, df_12mo):
        """
        Когда churn_rate is None — используется 0.05.
        Section 10: "Churn fallback: churn_rate is None → use 0.05."
        """
        with patch("app.core.forecast.calculate_churn_rate", return_value=None):
            result = generate_forecast(df_12mo)
            assert result is not None
            # churn_rate_used должен быть 0.05
            churn_used = result.get("churn_rate_used")
            assert churn_used == 0.05, (
                f"При churn_rate=None должен использоваться fallback 0.05, "
                f"получено: {churn_used} (Section 10)"
            )


# ===========================================================================
# БЛОК 6: HoltWinters Exception Handling — НОВЫЕ ТЕСТЫ v2.9
# Section 10 / Section 1 (Changelog v2.9 — FIXED): обязательный try/except
# для ValueError и numpy.linalg.LinAlgError
# Section 17: test_holtwinters_value_error_returns_none (NEW),
#             test_holtwinters_linalg_error_returns_none (NEW)
# ===========================================================================

class TestHoltWintersExceptionHandling:
    """
    НОВЫЕ тесты v2.9 — Section 1 (Changelog), Section 10, Section 17.
    Обязательная обработка ValueError и numpy.linalg.LinAlgError.
    При любом исключении: return None + st.warning с конкретным текстом.
    """

    def test_holtwinters_value_error_returns_none(self, df_degenerate):
        """
        HoltWinters вызывает ValueError (напр., идентичные значения) →
        generate_forecast должна вернуть None.
        Section 10: "On any exception → return None"
        Section 1 (v2.9 FIXED): "Forecast function now specifies mandatory
        try/except for ValueError and numpy.linalg.LinAlgError."
        Section 17: test_holtwinters_value_error_returns_none (NEW).
        """
        hw_path = "statsmodels.tsa.holtwinters.ExponentialSmoothing"
        with patch(hw_path) as mock_hw:
            # Имитируем ValueError при fit()
            mock_instance = MagicMock()
            mock_instance.fit.side_effect = ValueError(
                "Degenerate data: all values identical"
            )
            mock_hw.return_value = mock_instance

            result = generate_forecast(df_degenerate)

        assert result is None, (
            "generate_forecast должна вернуть None при ValueError в HoltWinters "
            "(Section 10, Section 1 v2.9)"
        )

    def test_holtwinters_value_error_returns_none_via_fixture(self):
        """
        Тест через fixture sample_degenerate_forecast.csv.
        Section 17: fixtures/sample_degenerate_forecast.csv — "Identical MRR values
        — triggers HoltWinters ValueError guard (NEW)."
        """
        try:
            df = _load_fixture("sample_degenerate_forecast.csv")
        except FileNotFoundError:
            pytest.skip("Fixture sample_degenerate_forecast.csv не найдена")

        hw_path = "statsmodels.tsa.holtwinters.ExponentialSmoothing"
        with patch(hw_path) as mock_hw:
            mock_instance = MagicMock()
            mock_instance.fit.side_effect = ValueError("Identical MRR values")
            mock_hw.return_value = mock_instance

            result = generate_forecast(df)

        assert result is None, (
            "generate_forecast должна вернуть None при ValueError "
            "(Section 17 fixture: sample_degenerate_forecast.csv)"
        )

    def test_holtwinters_value_error_shows_warning(self, df_degenerate):
        """
        При ValueError HoltWinters — должен отображаться st.warning с точным текстом.
        Section 10: "show st.warning('Forecast could not be computed for this dataset
        — data pattern is incompatible with the model.')"
        Section 1 (v2.9 FIXED): текст предупреждения зафиксирован.
        """
        expected_warning = (
            "Forecast could not be computed for this dataset "
            "— data pattern is incompatible with the model."
        )
        hw_path = "statsmodels.tsa.holtwinters.ExponentialSmoothing"
        with patch(hw_path) as mock_hw, patch("app.core.forecast.st") as mock_st:
            mock_instance = MagicMock()
            mock_instance.fit.side_effect = ValueError("Degenerate")
            mock_hw.return_value = mock_instance

            generate_forecast(df_degenerate)

        mock_st.warning.assert_called_with(expected_warning), (
            "Текст st.warning при ValueError должен точно соответствовать "
            "спецификации (Section 10, Section 1 v2.9)"
        )

    def test_holtwinters_linalg_error_returns_none(self, df_degenerate):
        """
        HoltWinters вызывает numpy.linalg.LinAlgError →
        generate_forecast должна вернуть None.
        Section 10: "On any exception → return None"
        Section 1 (v2.9 FIXED): "try/except for ValueError and
        numpy.linalg.LinAlgError."
        Section 17: test_holtwinters_linalg_error_returns_none (NEW).
        """
        hw_path = "statsmodels.tsa.holtwinters.ExponentialSmoothing"
        with patch(hw_path) as mock_hw:
            mock_instance = MagicMock()
            # Имитируем LinAlgError при fit()
            mock_instance.fit.side_effect = np.linalg.LinAlgError(
                "SVD did not converge"
            )
            mock_hw.return_value = mock_instance

            result = generate_forecast(df_degenerate)

        assert result is None, (
            "generate_forecast должна вернуть None при LinAlgError в HoltWinters "
            "(Section 10, Section 1 v2.9)"
        )

    def test_holtwinters_linalg_error_shows_warning(self, df_degenerate):
        """
        При LinAlgError HoltWinters — должен отображаться st.warning с точным текстом.
        Section 10: "show st.warning('Forecast could not be computed...')"
        """
        expected_warning = (
            "Forecast could not be computed for this dataset "
            "— data pattern is incompatible with the model."
        )
        hw_path = "statsmodels.tsa.holtwinters.ExponentialSmoothing"
        with patch(hw_path) as mock_hw, patch("app.core.forecast.st") as mock_st:
            mock_instance = MagicMock()
            mock_instance.fit.side_effect = np.linalg.LinAlgError(
                "SVD did not converge"
            )
            mock_hw.return_value = mock_instance

            generate_forecast(df_degenerate)

        mock_st.warning.assert_called_with(expected_warning), (
            "Текст st.warning при LinAlgError должен точно соответствовать "
            "спецификации (Section 10)"
        )

    def test_holtwinters_exception_does_not_propagate(self, df_degenerate):
        """
        Исключения HoltWinters НЕ должны всплывать наружу (нет unhandled crash).
        Section 1 (v2.9 FIXED): "Previously unspecified — would have surfaced as
        unhandled 500-level crash in production."
        """
        hw_path = "statsmodels.tsa.holtwinters.ExponentialSmoothing"
        for exc in [ValueError("v"), np.linalg.LinAlgError("l")]:
            with patch(hw_path) as mock_hw:
                mock_instance = MagicMock()
                mock_instance.fit.side_effect = exc
                mock_hw.return_value = mock_instance

                # Не должно бросать исключений
                try:
                    result = generate_forecast(df_degenerate)
                    assert result is None
                except (ValueError, np.linalg.LinAlgError) as e:
                    pytest.fail(
                        f"Исключение {type(e).__name__} не было перехвачено "
                        f"в generate_forecast (Section 10, Section 1 v2.9)"
                    )


# ===========================================================================
# БЛОК 7: Export gate — footer при < 6 месяцев
# Section 10: "Footer: 'Forecast omitted — fewer than 6 months of data available.'"
# ===========================================================================

class TestExportGate:
    """
    Тесты блокировки экспорта прогноза.
    Section 10: "Export gate: forecast_dict = None when data_months_used < 6."
    Section 17: test_export_gate_blocks_under_6mo.
    """

    def test_export_gate_blocks_under_6mo(self, df_5mo):
        """
        forecast_dict должен быть None или содержать export_ready=False при < 6 мес.
        Section 10: "Export gate: forecast_dict = None when data_months_used < 6."
        Section 17: test_export_gate_blocks_under_6mo.
        """
        result = generate_forecast(df_5mo)
        if result is not None:
            assert result.get("export_ready") is False, (
                "export_ready должен быть False при data_months_used < 6 "
                "(Section 10)"
            )

    def test_export_gate_passes_at_6mo(self, df_6mo):
        """
        При ≥ 6 месяцах экспорт должен быть разрешён.
        Section 10: "Export enabled" при ≥ 6 months.
        """
        result = generate_forecast(df_6mo)
        if result is not None:
            assert result.get("export_ready") is True, (
                "export_ready должен быть True при data_months_used >= 6 "
                "(Section 10)"
            )

    def test_footer_text_when_blocked(self, df_5mo):
        """
        Footer-текст при заблокированном экспорте.
        Section 10: "Footer: 'Forecast omitted — fewer than 6 months of data available.'"
        """
        result = generate_forecast(df_5mo)
        if result is not None and not result.get("export_ready", True):
            footer = result.get("export_footer", "")
            assert footer == "Forecast omitted — fewer than 6 months of data available.", (
                "Footer текст при блокировке экспорта не совпадает со спецификацией "
                "(Section 10)"
            )


# ===========================================================================
# БЛОК 8: Интеграционные тесты с реальными фикстурами
# Section 17: описание всех fixture-файлов
# ===========================================================================

class TestWithFixtures:
    """
    Интеграционные тесты с CSV-фикстурами.
    Section 17: tests/fixtures/
    """

    def test_basic_fixture_forecast(self):
        """
        Тест на sample_basic.csv — 500 rows, 12 months, чистые данные.
        Section 17: "sample_basic.csv — 500 rows, USD, 12 months, clean — happy path."
        """
        try:
            df = _load_fixture("sample_basic.csv")
        except FileNotFoundError:
            pytest.skip("Fixture sample_basic.csv не найдена")

        result = generate_forecast(df)
        assert result is not None, (
            "На clean 12-месячных данных прогноз не должен быть None "
            "(sample_basic.csv, Section 17)"
        )
        assert "realistic" in result
        assert len(result["realistic"]) == 12

    def test_sparse_fixture_returns_none(self):
        """
        sample_sparse.csv — 2 месяца → должен вернуть None.
        Section 17: "sample_sparse.csv — 50 rows, 2 months — minimum data guard."
        """
        try:
            df = _load_fixture("sample_sparse.csv")
        except FileNotFoundError:
            pytest.skip("Fixture sample_sparse.csv не найдена")

        result = generate_forecast(df)
        assert result is None, (
            "На sparse данных (2 месяца) прогноз должен быть None "
            "(sample_sparse.csv, Section 17)"
        )

    def test_degenerate_fixture_returns_none(self):
        """
        sample_degenerate_forecast.csv — идентичные значения → ValueError guard.
        Section 17: "sample_degenerate_forecast.csv — Identical MRR values (NEW)."
        Section 1 (v2.9): HoltWinters exception handling FIXED.
        """
        try:
            df = _load_fixture("sample_degenerate_forecast.csv")
        except FileNotFoundError:
            pytest.skip("Fixture sample_degenerate_forecast.csv не найдена")

        result = generate_forecast(df)
        assert result is None, (
            "На вырожденных данных прогноз должен быть None "
            "(sample_degenerate_forecast.csv, Section 17)"
        )

    def test_gap_fixture_handles_missing_month(self):
        """
        sample_gap.csv — Jan, Feb, Apr (нет March).
        Section 17: "sample_gap.csv — Jan, Feb, Apr — prev_month_status = 'gap'."
        Прогноз не должен падать с unhandled exception.
        """
        try:
            df = _load_fixture("sample_gap.csv")
        except FileNotFoundError:
            pytest.skip("Fixture sample_gap.csv не найдена")

        # Не должно бросать исключений
        try:
            result = generate_forecast(df)
            # None допустимо — мало данных, либо gap мешает
            assert result is None or isinstance(result, dict)
        except Exception as e:
            pytest.fail(
                f"generate_forecast не должна бросать исключений на gap-данных: "
                f"{type(e).__name__}: {e}"
            )
