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
# _compute_time_context — чистый детерминированный хелпер (Section 9)
# calculate_arpu, calculate_mrr — базовые метрики (Section 6)
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
    # Формулы из Section 6
    base_mrr: float = calculate_mrr(df)
    base_arpu: float = calculate_arpu(df)

    # ─── 3. GUARD: base_arpu == 0 (NEW in v2.9, Section 11) ──────────────────
    # Если ARPU равен нулю, price_increase невозможен — возвращаем None.
    # new_arpu = 0 * (1 + price_increase) = 0 → тихо даёт неверный результат.
    # Явная защита обязательна по спецификации.
    if base_arpu == 0:
        st.warning(
            "ARPU is zero — price increase cannot be modelled. "
            "Upload data with non-zero active amounts."
        )
        return None

    # ─── 4. Получаем базовый churn_rate ───────────────────────────────────────
    # Churn rate берём из метрик. Если None (нет предыдущего месяца / gap),
    # используем fallback 5.0% — аналогично правилу из Section 10 (Churn fallback).
    # Section 6: calculate_churn_rate возвращает float or None.
    raw_churn = calculate_churn_rate(df)
    # Fallback: churn_rate is None → используем 5.0% (Section 10, Churn fallback)
    base_churn_rate: float = raw_churn if raw_churn is not None else 5.0

    # Переводим churn_rate из процентов в долю (0–1)
    base_churn_fraction: float = base_churn_rate / 100.0

    # ─── 5. Вычисляем параметры симуляции ─────────────────────────────────────
    # Section 11: new_churn_rate = base_churn_rate * (1 - churn_reduction)
    # При churn_reduction=1.0 → new_churn_rate=0.0 → base MRR не убывает (корректно).
    new_churn_fraction: float = base_churn_fraction * (1.0 - churn_reduction)

    # Section 11: new_arpu = base_arpu * (1 + price_increase)
    # GUARD выше гарантирует base_arpu != 0
    new_arpu: float = base_arpu * (1.0 + price_increase)

    # ─── 6. 12-месячный прогон симуляции ──────────────────────────────────────
    # Section 11: Base MRR экспоненциально убывает каждый месяц на new_churn_rate.
    # Это корректное SaaS-моделирование оттока (cohort-based churn formula).
    #
    # Формула для месяца N:
    #   mrr_existing(N) = base_mrr * (1 - new_churn_fraction) ^ N
    #   mrr_new_customers(N) = накопленный MRR от new_customers_month × new_arpu
    #
    # Примечание: "cohort-based" означает, что каждый месяц теряется доля
    # от ТЕКУЩЕЙ базы, а не от исходной — реализовано через итеративный расчёт.

    months: list[int] = list(range(1, 13))  # месяцы 1–12
    mrr_values: list[float] = []

    # Накопленные подписчики из новых клиентов (растут каждый месяц)
    cumulative_new_subscribers: float = 0.0

    # Количество существующих подписчиков на старте симуляции.
    # Section 11: price_increase изменяет ARPU для всей базы — существующие
    # подписчики переходят на new_arpu. Поэтому стартовую базу храним в
    # единицах "подписчиков", а MRR вычисляем через new_arpu каждый месяц.
    # base_arpu != 0 гарантирован GUARD выше (Section 11).
    base_subscribers: float = base_mrr / base_arpu

    # Текущее количество существующих подписчиков (убывает от оттока)
    current_existing_subscribers: float = base_subscribers

    for month in months:
        # Существующая база убывает на new_churn_fraction за месяц (Section 11:
        # cohort-based churn formula — каждый месяц теряется доля от ТЕКУЩЕЙ базы)
        current_existing_subscribers = current_existing_subscribers * (
            1.0 - new_churn_fraction
        )

        # Новые клиенты добавляются каждый месяц
        cumulative_new_subscribers += new_customers_month

        # Все подписчики (существующие + новые) оцениваются по new_arpu.
        # Это корректно отражает price_increase: даже без новых клиентов
        # monthly_mrr[0] растёт при price_increase > 0 (Section 11).
        mrr_existing: float = current_existing_subscribers * new_arpu

        # MRR от новых клиентов также подвержен оттоку в следующих месяцах —
        # упрощённо: считаем, что новые подписчики добавляются в начале месяца
        # и сразу попадают под общий new_churn_fraction (консервативная оценка).
        mrr_new: float = cumulative_new_subscribers * new_arpu * (
            1.0 - new_churn_fraction
        )

        total_mrr: float = mrr_existing + mrr_new
        # Защита от отрицательных значений (аналог negative guard из Section 10)
        mrr_values.append(max(0.0, total_mrr))

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
    # Ключ "monthly_mrr" — основное имя списка MRR по месяцам (ожидается тестами).
    # Ключ "mrr_values" сохранён как алиас для обратной совместимости с UI-кодом,
    # который обращается к нему напрямую (5_dashboard.py, pdf_builder.py).
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
        # Результаты по месяцам — список из 12 значений MRR (Section 11).
        # "monthly_mrr" — каноническое имя ключа, которое проверяют тесты
        # (test_result_dict_contains_required_keys, test_simulation_horizon_12_months и др.)
        "monthly_mrr": mrr_values,
        # "mrr_values" — алиас, сохранён для совместимости с существующим UI-кодом.
        # Оба ключа указывают на один и тот же объект — дублирования памяти нет.
        "mrr_values": mrr_values,
        # Список номеров месяцев (1–12) для оси X на графике
        "months": months,
        # Итог
        "final_mrr": final_mrr,
        "mrr_change_pct": mrr_change_pct,            # None если base_mrr == 0
        # Временной контекст (для меток на графике)
        "time_context": time_ctx,
    }

    return simulation_result
