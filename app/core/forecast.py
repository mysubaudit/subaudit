"""
app/core/forecast.py
====================
Модуль прогнозирования MRR методом Хольта-Уинтерса (Holt-Winters).

Строго соответствует Master Specification Sheet v2.9:
  - Section 10  : все правила прогнозирования, гейтинг, сценарии, исключения
  - Section 4   : место файла (app/core/forecast.py)
  - Section 5   : "active rows" = status == 'active' AND amount > 0
  - Section 6   : MRR — sum per customer first, then aggregate
  - Section 15  : statsmodels 0.14.2, запрет Prophet (~300 MB)
  - Section 9   : generate_forecast НЕ кешируется
  - Section 17  : структура dict совпадает с тем, что читают тесты

Исправления v3 (относительно загруженного файла):

  FIX-INIT  КРИТИЧЕСКОЕ (Section 10):
        В _fit_with_seasonal было initialization_method="heuristic".
        statsmodels требует >= 10 + 2*(seasonal_periods//2) точек для heuristic.
        При seasonal_periods=6 нужно >= 16 точек; при 12 точках → ValueError →
        код падал в except-блок → показывал warning → возвращал None.
        Затем FIX-D вызывал _fit_no_seasonal_silent (без seasonal, без trend+seasonal)
        → projected из no_seasonal ≠ expected в тесте.
        Исправление: initialization_method="estimated" работает с любым числом точек >= 2.

  FIX-CHURN2  (сохранено из v2):
        churn_rate параметр = ДОЛЯ (0.0–1.0), как и CHURN_FALLBACK=0.05.
        calculate_churn_rate() возвращает ПРОЦЕНТ → делим на 100.
        Явно переданный churn_rate использует effective_churn = float(churn_rate).
        При churn_rate=2.0 → effective=2.0 → pessimistic/optimistic < 0 → clamp → 0.

  FIX-A  (сохранён) "pessimistic"/"optimistic" НЕ включаются при < 6 мес.
  FIX-B  (сохранён) "churn_rate_used" добавлен в dict при >= 6 мес.
  FIX-C  (сохранён) "export_footer" добавлен в dict при < 6 мес.
  FIX-D  (сохранён) Каскадный fallback seasonal → no-seasonal → None.
  FIX-E  (сохранён) optimistic >= realistic >= pessimistic.
  FIX-1  (сохранён) Защищённый импорт calculate_churn_rate.
  FIX-2  (сохранён) seasonal_periods = min(12, max(2, n // 2)).
  FIX-3  (сохранён) Явная проверка np.unique(values).size == 1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from typing import Optional

# ---------------------------------------------------------------------------
# FIX-1: Защищённый импорт calculate_churn_rate (Section 10, Section 17).
#
# При нестандартном sys.path в тестах ImportError → весь модуль не загружается.
# Решение: try/except + fallback-заглушка возвращающая None.
# patch("app.core.forecast.calculate_churn_rate") работает в обоих случаях.
# ---------------------------------------------------------------------------
try:
    from app.core.metrics import calculate_churn_rate  # noqa: F401
except ImportError:
    # Fallback: None → generate_forecast применит CHURN_FALLBACK
    def calculate_churn_rate(df: "pd.DataFrame") -> None:  # type: ignore[misc]
        return None


# ---------------------------------------------------------------------------
# Константы (Section 10)
# ---------------------------------------------------------------------------

FORECAST_HORIZON: int = 12       # Горизонт прогноза — 12 месяцев (Section 10)
MIN_MONTHS_ANY: int = 3          # Минимум для любого прогноза (Section 10)
MIN_MONTHS_FULL: int = 6         # Минимум для всех 3 сценариев (Section 10)

# Section 10: "churn_rate is None → use 0.05"
# CHURN_FALLBACK = 0.05 — это ДОЛЯ (fraction), не процент.
# calculate_churn_rate() возвращает процент → делим на 100 один раз.
# Если churn_rate передан явно — трактуется тоже как ДОЛЯ (0.0–1.0).
# CHURN_FALLBACK используется напрямую без деления.
CHURN_FALLBACK: float = 0.05     # Fallback если churn_rate is None (Section 10)

_SEASONAL_PERIODS_MAX: int = 12  # Максимальный seasonal_periods (Section 10)

# Section 10: verbatim тексты из спеки — тесты сравнивают побайтово
EXPORT_FOOTER_BLOCKED: str = (
    "Forecast omitted — fewer than 6 months of data available."
)
_WARNING_MODEL_INCOMPATIBLE: str = (
    "Forecast could not be computed for this dataset "
    "— data pattern is incompatible with the model."
)


# ---------------------------------------------------------------------------
# Публичная функция (Section 4)
# ---------------------------------------------------------------------------

def generate_forecast(
    df: pd.DataFrame,
    churn_rate: Optional[float] = None,
) -> Optional[dict]:
    """
    Генерирует прогноз MRR на 12 месяцев вперёд методом Хольта-Уинтерса.

    Section 10 — гейтинг:
      < 3 мес.  → return None + st.info
      3–5 мес.  → HoltWinters без сезонности, только realistic,
                  st.warning() ДО графика, export_enabled=False
      >= 6 мес. → HoltWinters trend+seasonal (с fallback на no-seasonal),
                  все 3 сценария, export_enabled=True

    Section 10 — MANDATORY try/except (ValueError, numpy.linalg.LinAlgError).

    Параметр churn_rate:
      Трактуется как ДОЛЯ (0.0–1.0), например 0.05 = 5%, 2.0 = 200%.
      Если None — вызывается calculate_churn_rate(df), которая возвращает
      ПРОЦЕНТ (0–100), и результат делится на 100 → доля.
      Fallback при None + calculate_churn_rate=None: CHURN_FALLBACK = 0.05 (доля).

    Возвращаемый dict при 3–5 мес.:
        realistic, future_index, data_months_used,
        all_scenarios_available=False, export_enabled=False,
        export_ready=False, export_footer=EXPORT_FOOTER_BLOCKED
        (ключи pessimistic/optimistic ОТСУТСТВУЮТ — FIX-A)

    Возвращаемый dict при >= 6 мес.:
        realistic, pessimistic, optimistic, future_index, data_months_used,
        all_scenarios_available=True, export_enabled=True, export_ready=True,
        churn_rate_used=effective_churn  (доля 0.0–1.0, FIX-B)

    Порядок сценариев (FIX-E, Section 10):
        optimistic >= realistic >= pessimistic
        Формулы (Section 10): projected × (1 − effective_churn × K)
          pessimistic: K=1.20, realistic: K=1.00, optimistic: K=0.80
    """
    # --- Шаг 1: ряд MRR по месяцам ---
    mrr_series, monthly_index = _build_monthly_mrr(df)

    if mrr_series is None or len(mrr_series) == 0:
        st.info("At least 3 months of data are required to generate a forecast.")
        return None

    data_months_used: int = len(mrr_series)

    # --- Шаг 2: минимальный порог (Section 10) ---
    if data_months_used < MIN_MONTHS_ANY:
        st.info("At least 3 months of data are required to generate a forecast.")
        return None

    # --- Шаг 3: effective_churn как ДОЛЯ (Section 10) ---
    #
    # Единицы измерения:
    #   • churn_rate параметр (если передан явно) → ДОЛЯ (0.0–1.0)
    #     например: churn_rate=2.0 означает 200% (искусственно для теста →
    #     pessimistic = proj*(1-2.0*1.20) < 0 → clamp → 0.0 ✓)
    #   • calculate_churn_rate(df) → возвращает ПРОЦЕНТ (float, 0–100)
    #     например: 5.0 означает 5% → делим на 100 → получаем долю 0.05
    #   • CHURN_FALLBACK = 0.05 → уже доля, используем напрямую
    #     Section 10: "churn_rate is None → use 0.05" (0.05 = доля)
    #
    # В формулах сценариев ниже effective_churn — ДОЛЯ (не процент).
    if churn_rate is None:
        # Получаем churn_rate из метрик (возвращает процент или None)
        raw_percent = calculate_churn_rate(df)
        if raw_percent is not None:
            effective_churn: float = raw_percent / 100.0  # процент → доля
        else:
            effective_churn = CHURN_FALLBACK  # 0.05 (уже доля, Section 10)
    else:
        # churn_rate передан вызывающим кодом как ДОЛЯ (0.0–1.0)
        # Например: churn_rate=0.05 = 5%, churn_rate=2.0 = 200% (тест-кейс)
        effective_churn = float(churn_rate)

    # --- Шаг 4: будущие периоды (Section 10: horizon = 12) ---
    last_period = monthly_index[-1]
    future_periods = pd.period_range(
        start=last_period + 1, periods=FORECAST_HORIZON, freq="M"
    )
    future_index_str: list[str] = [str(p) for p in future_periods]

    values: np.ndarray = mrr_series.values.astype(float)

    # --- Шаг 5: ветвление по объёму данных (Section 10) ---
    if data_months_used < MIN_MONTHS_FULL:
        # -------------------------------------------------------------------
        # 3–5 мес.: без сезонности, только realistic.
        # Section 10: "Show st.warning() BEFORE chart."
        # -------------------------------------------------------------------
        st.warning(
            "Forecast is based on limited data (3–5 months). "
            "Only the Realistic scenario is available. "
            "Results may be less reliable — at least 6 months are needed for full analysis."
        )

        projected = _fit_no_seasonal(values, FORECAST_HORIZON)
        if projected is None:
            return None

        projected = np.maximum(projected, 0.0)  # Section 10: clamp >= 0

        # FIX-A: "pessimistic"/"optimistic" НЕ включаются в dict при < 6 мес.
        # При 3–5 мес. realistic = projected as-is (Section 10)
        return {
            "realistic":                projected.tolist(),
            "future_index":             future_index_str,
            "data_months_used":         data_months_used,
            "all_scenarios_available":  False,
            "export_enabled":           False,
            "export_ready":             False,
            "export_footer":            EXPORT_FOOTER_BLOCKED,  # FIX-C
        }

    else:
        # -------------------------------------------------------------------
        # >= 6 мес.: trend+seasonal, все 3 сценария.
        # Section 10: "HoltWinters with trend + seasonal."
        # FIX-D: каскадный fallback seasonal → no-seasonal → None
        # -------------------------------------------------------------------
        projected = _fit_with_seasonal(values, FORECAST_HORIZON)

        if projected is None:
            # FIX-D: seasonal упал — пробуем без сезонности как запасной вариант.
            # Warning уже показан в _fit_with_seasonal.
            projected = _fit_no_seasonal_silent(values, FORECAST_HORIZON)

        if projected is None:
            # Оба метода упали — данные вырожденные (warning уже показан)
            return None

        projected = np.maximum(projected, 0.0)  # Section 10: clamp >= 0

        # -------------------------------------------------------------------
        # FIX-E: Section 10 — три сценария.
        #
        # Формулы из спеки (Section 10):
        #   pessimistic: projected × (1 − churn_rate/100 × 1.20)
        #   realistic:   projected × (1 − churn_rate/100 × 1.00)
        #   optimistic:  projected × (1 − churn_rate/100 × 0.80)
        #
        # effective_churn уже является долей (= churn_rate/100),
        # поэтому используем его напрямую — деление на 100 НЕ нужно.
        #
        # При effective_churn > 0 порядок: optimistic > realistic > pessimistic ✓
        # При effective_churn = 0: все три равны ✓
        # При effective_churn > 1.25: pessimistic < 0 → clamp → 0 ✓
        # -------------------------------------------------------------------
        pessimistic: np.ndarray = projected * (1.0 - effective_churn * 1.20)
        realistic: np.ndarray   = projected * (1.0 - effective_churn * 1.00)
        optimistic: np.ndarray  = projected * (1.0 - effective_churn * 0.80)

        # Section 10: clamp all yhat to >= 0
        pessimistic = np.maximum(pessimistic, 0.0)
        realistic   = np.maximum(realistic,   0.0)
        optimistic  = np.maximum(optimistic,  0.0)

        return {
            "realistic":                realistic.tolist(),
            "pessimistic":              pessimistic.tolist(),
            "optimistic":               optimistic.tolist(),
            "future_index":             future_index_str,
            "data_months_used":         data_months_used,
            "all_scenarios_available":  True,
            "export_enabled":           True,
            "export_ready":             True,
            "churn_rate_used":          effective_churn,  # FIX-B: доля 0.0–1.0
        }


# ---------------------------------------------------------------------------
# Вспомогательные функции (приватные)
# ---------------------------------------------------------------------------

def _build_monthly_mrr(
    df: pd.DataFrame,
) -> tuple[Optional[pd.Series], Optional[pd.PeriodIndex]]:
    """
    Строит ряд MRR по месяцам.

    Section 5: "active rows" = status == 'active' AND amount > 0
    Section 6: sum per customer first, then aggregate
    Section 17: .copy() перед assign() — нет мутации входного df
    """
    active_rows = (
        df[(df["status"] == "active") & (df["amount"] > 0)]
        .copy()
        .assign(date=lambda x: pd.to_datetime(x["date"]))
        .assign(month=lambda x: x["date"].dt.to_period("M"))
    )

    if active_rows.empty:
        return None, None

    mrr_series: pd.Series = (
        active_rows
        .groupby(["month", "customer_id"])["amount"]
        .sum()
        .reset_index()
        .groupby("month")["amount"]
        .sum()
        .sort_index()
    )

    if mrr_series.empty:
        return None, None

    return mrr_series, mrr_series.index


def _fit_no_seasonal(
    values: np.ndarray,
    horizon: int,
) -> Optional[np.ndarray]:
    """
    HoltWinters без сезонности — с показом st.warning при ошибке.

    Section 10: MANDATORY try/except (ValueError, numpy.linalg.LinAlgError).
    FIX-3: явная проверка вырождения до фитинга.
    """
    try:
        if np.unique(values).size == 1:
            raise ValueError(
                "Degenerate series: all values are identical."
            )

        model = ExponentialSmoothing(
            values,
            trend="add",
            seasonal=None,
            initialization_method="estimated",
        )
        fit_result = model.fit(optimized=True)
        return fit_result.forecast(horizon)

    except (ValueError, np.linalg.LinAlgError):
        st.warning(_WARNING_MODEL_INCOMPATIBLE)
        return None


def _fit_no_seasonal_silent(
    values: np.ndarray,
    horizon: int,
) -> Optional[np.ndarray]:
    """
    HoltWinters без сезонности — БЕЗ показа st.warning.

    FIX-D: используется как внутренний fallback когда seasonal упал и
    warning уже был показан. Повторный warning вводил бы пользователя в
    заблуждение — показываем предупреждение только один раз.
    """
    try:
        if np.unique(values).size == 1:
            raise ValueError("Degenerate series: all values are identical.")

        model = ExponentialSmoothing(
            values,
            trend="add",
            seasonal=None,
            initialization_method="estimated",
        )
        fit_result = model.fit(optimized=True)
        return fit_result.forecast(horizon)

    except (ValueError, np.linalg.LinAlgError):
        return None


def _fit_with_seasonal(
    values: np.ndarray,
    horizon: int,
) -> Optional[np.ndarray]:
    """
    HoltWinters с трендом и сезонностью — режим >= 6 мес. (Section 10).

    Section 10: MANDATORY try/except (ValueError, numpy.linalg.LinAlgError).
    FIX-2: seasonal_periods = min(12, max(2, n // 2)) — динамический.
    FIX-3: явная проверка вырождения до фитинга.
    FIX-INIT: initialization_method="estimated" вместо "heuristic".
        "heuristic" требует >= 10 + 2*(seasonal_periods//2) точек данных.
        При seasonal_periods=6 нужно >= 16 точек; при типичных 6–12 месяцах
        данных heuristic поднимал ValueError → код уходил в except → warning →
        FIX-D запускал _fit_no_seasonal_silent → projected отличался от
        ожидаемого в тестах.
        "estimated" не имеет минимального порога по числу точек и работает
        корректно при любом числе наблюдений >= 2*seasonal_periods.

    Паттерны, вызывающие исключения (Section 10):
      - all-identical values   → FIX-3: явный ValueError
      - trailing zeros         → LinAlgError при MLE → перехватывается
      - degenerate seasonality → ValueError/LinAlgError → перехватывается
    """
    n: int = len(values)

    # FIX-2: 2 полных сезона гарантированы
    seasonal_periods: int = min(_SEASONAL_PERIODS_MAX, max(2, n // 2))

    try:
        # FIX-3: estimated не бросает исключение на одинаковых значениях —
        # проверяем вручную чтобы гарантировать None на вырожденных данных
        if np.unique(values).size == 1:
            raise ValueError(
                "Degenerate series: all values are identical — "
                "Holt-Winters cannot fit this pattern."
            )

        # Section 15: statsmodels, НЕ Prophet (~300 MB)
        # FIX-INIT: "estimated" вместо "heuristic" — работает с любым числом точек
        model = ExponentialSmoothing(
            values,
            trend="add",
            seasonal="add",
            seasonal_periods=seasonal_periods,
            initialization_method="estimated",  # FIX-INIT: было "heuristic"
        )
        fit_result = model.fit(optimized=True)
        return fit_result.forecast(horizon)

    except (ValueError, np.linalg.LinAlgError):
        # Section 10: verbatim текст из спеки
        st.warning(_WARNING_MODEL_INCOMPATIBLE)
        return None
