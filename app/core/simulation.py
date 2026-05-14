"""
app/core/simulation.py
SubAudit — Master Specification Sheet v2.9
Раздел 11 (Simulation — PRO only), Раздел 5 (Core Definitions), Раздел 6 (Metric Formulas)
Development Order Step 4 (Section 16)

Только для PRO-пользователей (проверка плана выполняется на уровне 5_dashboard.py).
Этот модуль НЕ проверяет план — он лишь выполняет расчёт симуляции.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

# Импортируем вспомогательные функции из metrics.py
# _compute_time_context — чистый детерминированный хелпер, не кешируется (Section 9)
# calculate_arpu, calculate_mrr, calculate_churn_rate — базовые метрики (Section 6)
from app.core.metrics import (
    _compute_time_context,
    calculate_arpu,
    calculate_churn_rate,
    calculate_mrr,
)


def run_simulation(
    df: pd.DataFrame,
    churn_reduction: float,
    new_customers_month: int,
    price_increase: float,
) -> dict | None:
    """
    Запускает 12-месячную симуляцию роста MRR.

    Параметры (Section 11 — Input Parameters):
        df                  — очищенный датафрейм (df_clean из session_state)
        churn_reduction     — float [0.0–1.0]: снижение churn rate на эту долю
                              (0.20 = на 20% меньше отток)
        new_customers_month — int [0–10000]: дополнительных новых клиентов в месяц
        price_increase      — float [−0.5–5.0]: изменение ARPU
                              (0.10 = рост цены на 10%)

    Возвращает dict с результатами симуляции или None при критических условиях.

    GUARD: если base_arpu == 0 → возвращает None + показывает st.warning (Section 11).
    GUARD: если base_mrr == 0 → mrr_change_pct = None (Section 11).
    """

    # ─── 1. Получаем временной контекст ───────────────────────────────────────
    # _compute_time_context() — чистый хелпер, не кешируется (Section 9)
    time_ctx = _compute_time_context(df)

    # ─── 2. Вычисляем базовые показатели из реальных данных ───────────────────
    # Формулы из Section 6; df не мутируется (требование иммутабельности)
    base_mrr: float = calculate_mrr(df)
    base_arpu: float = calculate_arpu(df)

    # ─── 3. GUARD: base_arpu == 0 (NEW in v2.9, Section 11) ──────────────────
    # Если ARPU равен нулю, price_increase невозможен — возвращаем None немедленно.
    # Без этой защиты: new_arpu = 0 * (1 + price_increase) = 0 → тихо даёт
    # неверный результат. Явная защита обязательна по спецификации.
    if base_arpu == 0:
        st.warning(
            "ARPU is zero — price increase cannot be modelled. "
            "Upload data with non-zero active amounts."
        )
        return None

    # ─── 4. Получаем базовый churn_rate ───────────────────────────────────────
    # Section 6: calculate_churn_rate возвращает float or None.
    # Если None (нет предыдущего месяца или gap) — используем fallback 5%
    # по аналогии с правилом из Section 10 (Churn fallback).
    raw_churn = calculate_churn_rate(df)
    base_churn_rate: float = raw_churn if raw_churn is not None else 5.0  # в процентах

    # Переводим churn_rate из процентов в долю (0–1)
    base_churn_fraction: float = base_churn_rate / 100.0

    # ─── 5. Вычисляем параметры симуляции ─────────────────────────────────────
    # Section 11: new_churn_rate = base_churn_rate * (1 - churn_reduction)
    # При churn_reduction=1.0 → new_churn_fraction=0.0 → MRR не убывает (корректно,
    # Section 11: "At churn_reduction=1.0, new_churn_rate=0.0 and base MRR remains
    # constant — correct.")
    new_churn_fraction: float = base_churn_fraction * (1.0 - churn_reduction)

    # Section 11: new_arpu = base_arpu * (1 + price_increase)
    # GUARD выше гарантирует base_arpu != 0
    new_arpu: float = base_arpu * (1.0 + price_increase)

    # 6. 12-месячный прогон симуляции ──────────────────────────────────────
    # Section 11: "Base MRR decays exponentially each month by new_churn_rate —
    # correct SaaS churn modelling" / "cohort-based churn formula".
    #
    # ИСПРАВЛЕНО (2026-05-14): Churn применяется в КОНЦЕ месяца, а не в начале.
    # Месяц 1 показывает MRR на НАЧАЛО первого месяца (до churn).
    # Это даёт более точную симуляцию: новые клиенты не теряют churn в месяц добавления.
    #
    # Реализация cohort-based для ОБОИХ потоков (существующие + новые):
    #
    # Существующие подписчики:
    #   Месяц N показывает S₀ × (1-r)^(N-1) — churn применён (N-1) раз
    #   MRR_exist(N) = S_exist(N) * new_arpu
    #
    # Новые подписчики (cohort-based):
    #   Каждый месяц new_customers_month добавляются БЕЗ churn,
    #   затем весь пул убывает в КОНЦЕ месяца.
    #   Месяц 1: 50 клиентов (churn ещё не применён)
    #   Месяц 2: (50 + 50) × (1-r) после первого churn
    #   Месяц 3: ((50 + 50) × (1-r) + 50) × (1-r)

    months: list[int] = list(range(1, 13))  # месяцы 1–12
    mrr_values: list[float] = []
    monthly_data: list[dict] = []  # Детальные данные для Excel экспорта

    # Конвертируем base_mrr в количество подписчиков для корректного
    # применения price_increase (существующие клиенты переходят на new_arpu).
    # base_arpu != 0 гарантирован GUARD выше.
    current_existing_subscribers: float = base_mrr / base_arpu

    # Накопительный MRR от новых клиентов — убывает каждый месяц как cohort
    current_new_mrr: float = 0.0
    # Накопительное количество новых подписчиков (для отслеживания)
    cumulative_new_subscribers: float = 0.0

    prev_mrr: float = base_mrr  # Для расчёта MRR change

    for month in months:
        # Сначала вычисляем MRR на НАЧАЛО месяца (до применения churn)
        mrr_existing: float = current_existing_subscribers * new_arpu

        # Добавляем новых клиентов этого месяца (они ещё не испытали churn)
        cumulative_new_subscribers += new_customers_month
        current_new_mrr += new_customers_month * new_arpu

        # MRR на начало месяца = существующие + новые (до churn)
        total_mrr: float = mrr_existing + current_new_mrr

        # Защита от отрицательных значений
        total_mrr = max(0.0, total_mrr)
        mrr_values.append(total_mrr)

        # Расчёт изменений для детального отчёта
        mrr_change: float = total_mrr - prev_mrr
        mrr_change_pct: float | None = (
            (mrr_change / prev_mrr * 100.0) if prev_mrr != 0 else None
        )

        # Общее количество активных подписчиков на начало месяца
        total_active_subscribers: float = current_existing_subscribers + cumulative_new_subscribers

        # Сохраняем детальные данные для Excel
        monthly_data.append({
            "month": month,
            "mrr": total_mrr,
            "mrr_change": mrr_change,
            "mrr_change_pct": mrr_change_pct,
            "active_subscribers": round(total_active_subscribers),
            "new_customers_added": new_customers_month,
            "effective_churn_rate": new_churn_fraction * 100,  # в процентах
        })

        prev_mrr = total_mrr

        # ПОСЛЕ записи результатов месяца применяем churn к КОНЦУ месяца
        # (это повлияет на следующий месяц)
        current_existing_subscribers = current_existing_subscribers * (
            1.0 - new_churn_fraction
        )
        cumulative_new_subscribers = cumulative_new_subscribers * (
            1.0 - new_churn_fraction
        )
        current_new_mrr = current_new_mrr * (1.0 - new_churn_fraction)

    # ─── 7. Итоговый MRR через 12 месяцев ─────────────────────────────────────
    final_mrr: float = mrr_values[-1]

    # ─── 8. GUARD: mrr_change_pct = None когда base_mrr == 0 (Section 11) ─────
    # Деление на ноль запрещено. Отображать в st.metric delta как "N/A".
    if base_mrr == 0:
        mrr_change_pct: float | None = None
    else:
        mrr_change_pct = ((final_mrr - base_mrr) / base_mrr) * 100.0

    # ─── 9. Формируем результирующий словарь ──────────────────────────────────
    # Section 11: словарь содержит все параметры для Dashboard и PDF-экспорта.
    # "monthly_mrr" — каноническое имя ключа (Section 17: test_simulation.py).
    # "mrr_values" — алиас для совместимости с UI-кодом (5_dashboard.py,
    # pdf_builder.py). Оба ключа указывают на один объект — дублирования нет.
    # "monthly_data" — детальные данные для Excel экспорта (новое в v1.0).
    simulation_result: dict = {
        # Входные параметры (для отображения в UI и PDF)
        "churn_reduction": churn_reduction,
        "new_customers_month": new_customers_month,
        "price_increase": price_increase,
        # Базовые показатели
        "base_mrr": base_mrr,
        "base_arpu": base_arpu,
        "base_churn_rate": base_churn_rate,          # в процентах
        # Параметры симуляции
        "new_churn_rate": new_churn_fraction * 100,  # в процентах для отображения
        "new_arpu": new_arpu,
        # Результаты по месяцам — список из 12 значений MRR (Section 11, Section 17)
        "monthly_mrr": mrr_values,
        # Алиас для обратной совместимости с UI-кодом (5_dashboard.py, pdf_builder.py)
        "mrr_values": mrr_values,
        # Детальные данные по месяцам для Excel экспорта (v1.0)
        "monthly_data": monthly_data,
        # Список номеров месяцев (1–12) для оси X на графике
        "months": months,
        # Итог
        "final_mrr": final_mrr,
        "mrr_change_pct": mrr_change_pct,            # None если base_mrr == 0
        # Временной контекст (для меток на графике)
        "time_context": time_ctx,
    }

    return simulation_result
