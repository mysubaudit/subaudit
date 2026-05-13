"""
core/metrics.py
SubAudit — Master Specification Sheet v2.9
Development Order Step 4 (Section 16).

Реализует все метрики из Section 6, Section 7, Section 8.
Сигнатуры функций строго соответствуют Section 9.
Кэширование: только get_all_metrics() и get_data_quality_flags() — Section 9.
_compute_time_context() НЕ кэшируется — Section 9.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
from datetime import date
from dateutil.relativedelta import relativedelta


# ---------------------------------------------------------------------------
# Вспомогательная функция определения временного контекста
# НЕ кэшируется — Section 9: "Do NOT cache individual metric functions
# or _compute_time_context()"
# ---------------------------------------------------------------------------

def _compute_time_context(df: pd.DataFrame) -> dict:
    """
    Определяет last_month, prev_month и их статусы.

    Определения (Section 5):
    - last_month: самый свежий календарный месяц с ≥ 5 уникальными
      активными клиентами. Если таких нет — самый свежий месяц
      (fallback), записывается last_month_is_fallback=True.
    - prev_month: календарный месяц сразу ДО last_month по календарю
      (не по данным).
    - prev_month_status: 'ok' | 'missing' | 'gap'

    Возвращает dict с ключами:
      last_month          : pd.Period (месяц)
      last_month_is_fallback : bool
      prev_month          : pd.Period (месяц)
      prev_month_status   : 'ok' | 'missing' | 'gap'
    """
    # Только активные строки с amount > 0 (Section 5: "active rows")
    # .assign() вместо subscript-мутации — требование иммутабельности (Section 17)
    active = (
        df[(df["status"] == "active") & (df["amount"] > 0)]
        .assign(_period=lambda x: x["date"].dt.to_period("M"))
    )

    if active.empty:
        # Нет активных данных вообще — возвращаем заглушку
        return {
            "last_month": None,
            "last_month_is_fallback": True,
            "prev_month": None,
            "prev_month_status": "missing",
        }

    # Считаем уникальных активных клиентов по месяцам
    monthly_customers = (
        active.groupby("_period")["customer_id"]
        .nunique()
        .sort_index()
    )

    # Самый свежий месяц в данных (по всем месяцам, включая non-qualified)
    most_recent_month = monthly_customers.index[-1]

    # last_month — самый свежий месяц с ≥ 5 уникальными активными клиентами,
    # но ТОЛЬКО если это самый свежий месяц данных. (Section 5:
    # "Most recent calendar month with ≥ 5 unique active customers.
    #  FALLBACK: most recent month regardless")
    # Алгоритм: если самый свежий месяц qualified → last_month = он, не fallback.
    # Если нет → fallback = самый свежий месяц независимо от количества.
    qualified = monthly_customers[monthly_customers >= 5]

    if most_recent_month in qualified.index:
        # Самый свежий месяц имеет ≥ 5 клиентов — берём его
        last_month = most_recent_month
        last_month_is_fallback = False
    elif not qualified.empty:
        # Самый свежий месяц не qualified, но есть qualified месяцы ранее.
        # По спеке: FALLBACK — самый свежий месяц (most_recent_month).
        # Мы НЕ откатываемся к последнему qualified — это противоречит
        # "most recent month regardless" в fallback.
        last_month = most_recent_month
        last_month_is_fallback = True
    else:
        # Ни один месяц не имеет ≥ 5 клиентов — fallback
        last_month = most_recent_month
        last_month_is_fallback = True

    # prev_month — ровно месяц до last_month по календарю (Section 5)
    prev_month = last_month - 1

    # Определяем статус prev_month
    all_months_in_data = set(monthly_customers.index)

    if prev_month not in all_months_in_data:
        # Проверяем, был ли пропуск или просто нет данных вообще до last_month
        earlier = [m for m in all_months_in_data if m < last_month]
        if not earlier:
            prev_month_status = "missing"
        else:
            # Данные есть, но prev_month отсутствует — gap
            prev_month_status = "gap"
    else:
        prev_month_status = "ok"

    return {
        "last_month": last_month,
        "last_month_is_fallback": last_month_is_fallback,
        "prev_month": prev_month,
        "prev_month_status": prev_month_status,
    }


# ---------------------------------------------------------------------------
# Блок 1 — Revenue (Section 6, Section 9)
# ---------------------------------------------------------------------------

def calculate_mrr(df: pd.DataFrame) -> float:
    """
    MRR: сумма amount для всех активных строк в last_month.
    Несколько строк на клиента — сначала суммируем по клиенту,
    затем агрегируем. (Section 6)
    """
    ctx = _compute_time_context(df)
    last_month = ctx["last_month"]
    if last_month is None:
        return 0.0

    # .assign() вместо subscript-мутации — требование иммутабельности (Section 17)
    active = (
        df[(df["status"] == "active") & (df["amount"] > 0)]
        .assign(_period=lambda x: x["date"].dt.to_period("M"))
    )
    month_data = active[active["_period"] == last_month]

    if month_data.empty:
        return 0.0

    # Суммируем по клиенту, затем суммируем всё — Section 6
    per_customer = month_data.groupby("customer_id")["amount"].sum()
    return float(per_customer.sum())


def calculate_arr(df: pd.DataFrame) -> float:
    """
    ARR = MRR × 12 (Section 6)
    """
    return calculate_mrr(df) * 12.0


def calculate_arpu(df: pd.DataFrame) -> float:
    """
    ARPU = MRR ÷ count уникальных активных customer_id в last_month.
    Если count == 0 → возвращаем 0.0 (Section 6)
    """
    ctx = _compute_time_context(df)
    last_month = ctx["last_month"]
    if last_month is None:
        return 0.0

    # .assign() вместо subscript-мутации — требование иммутабельности (Section 17)
    active = (
        df[(df["status"] == "active") & (df["amount"] > 0)]
        .assign(_period=lambda x: x["date"].dt.to_period("M"))
    )
    month_data = active[active["_period"] == last_month]

    unique_count = month_data["customer_id"].nunique()
    if unique_count == 0:
        return 0.0

    mrr = calculate_mrr(df)
    return float(mrr / unique_count)


def calculate_total_revenue(df: pd.DataFrame) -> float:
    """
    Total Revenue: сумма всех положительных amount по всему времени
    и всем статусам. (Section 6)
    """
    return float(df[df["amount"] > 0]["amount"].sum())


# ---------------------------------------------------------------------------
# Блок 2 — Growth (Section 6, Section 9)
# ---------------------------------------------------------------------------

def _get_new_customer_ids(df: pd.DataFrame) -> set:
    """
    «Новый клиент» (Section 5): customer_id, встречающийся в датасете
    ВПЕРВЫЕ (любой статус, любое время).
    Возвращаем множество customer_id, чья первая запись приходится
    на last_month.
    """
    ctx = _compute_time_context(df)
    last_month = ctx["last_month"]
    if last_month is None:
        return set()

    # .assign() возвращает новый объект — нет side-effects (Section 17)
    data = df.assign(_period=df["date"].dt.to_period("M"))

    # Первое появление каждого клиента (по любому статусу)
    first_seen = data.groupby("customer_id")["_period"].min()
    new_ids = set(first_seen[first_seen == last_month].index)
    return new_ids


def _get_reactivated_customer_ids(df: pd.DataFrame, arpu: float) -> set:
    """
    «Реактивированный клиент» (Section 5):
    - customer_id с ≥ 1 активной строкой исторически,
    - отсутствовал в active rows 2–9 месяцев подряд включительно,
    - вновь появился как активный в last_month.
    - Annual detection: если max(amount) > 6 × ARPU → исключаем из
      реактивации независимо от длины отсутствия.
    """
    ctx = _compute_time_context(df)
    last_month = ctx["last_month"]
    if last_month is None:
        return set()

    # .assign() вместо subscript-мутации — требование иммутабельности (Section 17)
    active = (
        df[(df["status"] == "active") & (df["amount"] > 0)]
        .assign(_period=lambda x: x["date"].dt.to_period("M"))
    )

    # Клиенты, активные в last_month
    last_month_customers = set(
        active[active["_period"] == last_month]["customer_id"]
    )
    if not last_month_customers:
        return set()

    reactivated = set()

    for cid in last_month_customers:
        cid_active = active[active["customer_id"] == cid]

        # Исторические периоды присутствия (кроме last_month)
        historical_periods = set(cid_active["_period"].unique()) - {last_month}
        if not historical_periods:
            # Нет исторических активных записей — это новый, не реактивированный
            continue

        # Ищем последний период присутствия до last_month
        periods_before = [p for p in historical_periods if p < last_month]
        if not periods_before:
            continue

        last_present = max(periods_before)

        # Количество месяцев отсутствия.
        # (last_month - last_present).n — это разница в периодах.
        # Если клиент был в Jan и вернулся в Mar: разница = 2, но отсутствовал
        # 1 месяц (только Feb). Поэтому months_absent = разница - 1.
        months_absent = (last_month - last_present).n - 1

        # Отсутствие должно быть 2–9 месяцев включительно (Section 5)
        if not (2 <= months_absent <= 9):
            continue

        # Annual detection: если max(amount) > 6 × ARPU → исключаем (Section 5).
        # Используем переданный arpu напрямую — строго по спецификации.
        if arpu > 0:
            max_amount = cid_active["amount"].max()
            if max_amount > 6 * arpu:
                continue

        reactivated.add(cid)

    return reactivated


def calculate_new_mrr(df: pd.DataFrame) -> float:
    """
    New MRR: сумма amount активных строк в last_month, где customer_id
    является новым клиентом. НЕ включает реактивированных. (Section 6)
    """
    ctx = _compute_time_context(df)
    last_month = ctx["last_month"]
    if last_month is None:
        return 0.0

    new_ids = _get_new_customer_ids(df)
    if not new_ids:
        return 0.0

    # .assign() вместо subscript-мутации — требование иммутабельности (Section 17)
    active = (
        df[(df["status"] == "active") & (df["amount"] > 0)]
        .assign(_period=lambda x: x["date"].dt.to_period("M"))
    )
    month_data = active[active["_period"] == last_month]

    new_rows = month_data[month_data["customer_id"].isin(new_ids)]
    per_customer = new_rows.groupby("customer_id")["amount"].sum()
    return float(per_customer.sum())


def calculate_reactivation_mrr(df: pd.DataFrame, arpu: float) -> float:
    """
    Reactivation MRR: сумма amount активных строк в last_month,
    где customer_id является реактивированным клиентом.
    Входит в общий MRR, НЕ входит в New MRR. (Section 6)
    Сигнатура: (df, arpu: float) — Section 9.
    """
    ctx = _compute_time_context(df)
    last_month = ctx["last_month"]
    if last_month is None:
        return 0.0

    reactivated_ids = _get_reactivated_customer_ids(df, arpu)
    if not reactivated_ids:
        return 0.0

    # .assign() вместо subscript-мутации — требование иммутабельности (Section 17)
    active = (
        df[(df["status"] == "active") & (df["amount"] > 0)]
        .assign(_period=lambda x: x["date"].dt.to_period("M"))
    )
    month_data = active[active["_period"] == last_month]

    react_rows = month_data[month_data["customer_id"].isin(reactivated_ids)]
    per_customer = react_rows.groupby("customer_id")["amount"].sum()
    return float(per_customer.sum())


def calculate_growth_rate(df: pd.DataFrame) -> float | None:
    """
    Growth Rate = ((MRR_last − MRR_prev) ÷ MRR_prev) × 100
    Если MRR_prev == 0 OR prev_month_status != 'ok' → вернуть None. (Section 6)
    """
    ctx = _compute_time_context(df)
    if ctx["prev_month_status"] != "ok":
        return None

    last_month = ctx["last_month"]
    prev_month = ctx["prev_month"]

    # .assign() вместо subscript-мутации — требование иммутабельности (Section 17)
    active = (
        df[(df["status"] == "active") & (df["amount"] > 0)]
        .assign(_period=lambda x: x["date"].dt.to_period("M"))
    )

    def _mrr_for_period(period):
        rows = active[active["_period"] == period]
        if rows.empty:
            return 0.0
        return float(rows.groupby("customer_id")["amount"].sum().sum())

    mrr_last = _mrr_for_period(last_month)
    mrr_prev = _mrr_for_period(prev_month)

    if mrr_prev == 0:
        return None

    return float(((mrr_last - mrr_prev) / mrr_prev) * 100)


def calculate_new_subscribers(df: pd.DataFrame) -> int:
    """
    New Subscribers: количество уникальных новых customer_id
    (первое появление вообще, любой статус) в last_month. (Section 6)
    """
    return len(_get_new_customer_ids(df))


def calculate_reactivated_subscribers(df: pd.DataFrame, arpu: float) -> int:
    """
    Количество реактивированных клиентов в last_month. (Section 6)
    Сигнатура: (df, arpu: float) — Section 9.
    """
    return len(_get_reactivated_customer_ids(df, arpu))


# ---------------------------------------------------------------------------
# Блок 3 — Retention (Section 6, Section 8, Section 9)
# ---------------------------------------------------------------------------

def _get_active_customer_ids_for_period(
    df: pd.DataFrame, period: pd.Period
) -> set:
    """Возвращает множество активных customer_id для заданного периода."""
    # .assign() вместо subscript-мутации — требование иммутабельности (Section 17)
    active = (
        df[(df["status"] == "active") & (df["amount"] > 0)]
        .assign(_period=lambda x: x["date"].dt.to_period("M"))
    )
    return set(active[active["_period"] == period]["customer_id"])


def calculate_churn_rate(df: pd.DataFrame) -> float | None:
    """
    Churn Rate = (lost_subscribers ÷ active_prev_month) × 100
    Если active_prev_month == 0 OR prev_month_status != 'ok' → None. (Section 6)
    """
    ctx = _compute_time_context(df)
    if ctx["prev_month_status"] != "ok":
        return None

    prev_month = ctx["prev_month"]
    last_month = ctx["last_month"]

    active_prev = _get_active_customer_ids_for_period(df, prev_month)
    if not active_prev:
        return None

    active_last = _get_active_customer_ids_for_period(df, last_month)
    lost = active_prev - active_last

    return float((len(lost) / len(active_prev)) * 100)


def calculate_revenue_churn(df: pd.DataFrame) -> float:
    """
    Revenue Churn — четыре сценария A/B/C/D (Section 8).
    Сигнатура: (df) — контекст получаем через _compute_time_context(df).
    Group B ограничен строго last_month — кросс-периодные рефанды исключены.

    A — Активен в prev_month, отсутствует в last_month, без рефанда
        → amount prev_month
    B — Отрицательный amount в last_month, НЕ в churned-множестве
        → abs(refund amount)
    C — В churned-множестве И отрицательный amount в last_month
        → только prev_month active amount (без добавления рефанда)
    D — Рефанд в прошлом периоде + churn в last_month
        → только prev_month active amount (логика A)
    """
    ctx = _compute_time_context(df)
    if ctx["prev_month_status"] != "ok":
        return 0.0

    prev_month = ctx["prev_month"]
    last_month = ctx["last_month"]

    # .assign() вместо subscript-мутации — требование иммутабельности (Section 17)
    active = (
        df[(df["status"] == "active") & (df["amount"] > 0)]
        .assign(_period=lambda x: x["date"].dt.to_period("M"))
    )

    # .assign() возвращает новый объект — нет side-effects (Section 17)
    data = df.assign(_period=df["date"].dt.to_period("M"))

    # Активные клиенты prev_month
    prev_active_rows = active[active["_period"] == prev_month]
    prev_active_customers = set(prev_active_rows["customer_id"])

    # Активные клиенты last_month — для определения churned_set используем
    # status=='active' (любой amount). Клиент с рефандом (amount<0) но
    # status='active' НЕ является churned — он остался клиентом (Section 8, Scenario B).
    # Отличие от active_rows (amount>0): здесь нас интересует факт присутствия
    # клиента в отношениях, а не вхождение в MRR.
    data_last = data[data["_period"] == last_month]
    last_status_active_customers = set(
        data_last[data_last["status"] == "active"]["customer_id"]
    )

    # Churned set: активны в prev_month, отсутствуют как status='active' в last_month
    churned_set = prev_active_customers - last_status_active_customers

    # Prev month amount per customer
    prev_amounts = (
        prev_active_rows.groupby("customer_id")["amount"].sum().to_dict()
    )

    # Строки с отрицательным amount в last_month (только last_month — Section 8)
    refund_rows_last = data[
        (data["_period"] == last_month) & (data["amount"] < 0)
    ]
    refund_customers_last = set(refund_rows_last["customer_id"])

    revenue_lost = 0.0

    # Сценарии A и C: обходим churned_set
    for cid in churned_set:
        prev_amount = prev_amounts.get(cid, 0.0)
        if cid in refund_customers_last:
            # Сценарий C: churned + refund в last_month → только prev amount
            revenue_lost += prev_amount
        else:
            # Сценарий A (и D — cross-period refund): только prev amount
            revenue_lost += prev_amount

    # Сценарий B: рефанд в last_month, клиент НЕ в churned_set
    for _, row in refund_rows_last.iterrows():
        cid = row["customer_id"]
        if cid not in churned_set:
            revenue_lost += abs(row["amount"])

    return float(revenue_lost)


def calculate_nrr(df: pd.DataFrame) -> float | None:
    """
    NRR = CLAMP(((MRR_last − revenue_churn + expansion_mrr) ÷ MRR_prev) × 100, 0, 999)
    expansion_mrr = 0 в v1.
    Если MRR_prev == 0 или prev_month_status != 'ok' → None. (Section 6)
    Предупреждение при NRR > 200%. (Section 6)
    """
    ctx = _compute_time_context(df)
    if ctx["prev_month_status"] != "ok":
        return None

    prev_month = ctx["prev_month"]
    last_month = ctx["last_month"]

    # .assign() вместо subscript-мутации — требование иммутабельности (Section 17)
    active = (
        df[(df["status"] == "active") & (df["amount"] > 0)]
        .assign(_period=lambda x: x["date"].dt.to_period("M"))
    )

    def _mrr_period(period):
        rows = active[active["_period"] == period]
        if rows.empty:
            return 0.0
        return float(rows.groupby("customer_id")["amount"].sum().sum())

    mrr_prev = _mrr_period(prev_month)
    if mrr_prev == 0:
        return None

    mrr_last = _mrr_period(last_month)
    revenue_churn = calculate_revenue_churn(df)
    expansion_mrr = 0.0  # v1: всегда 0

    raw_nrr = ((mrr_last - revenue_churn + expansion_mrr) / mrr_prev) * 100
    nrr = float(np.clip(raw_nrr, 0.0, 999.0))

    # Предупреждение при NRR > 200% — выводим здесь (Section 6).
    # Тест test_nrr_display_warning_above_200 проверяет вызов st.warning()
    # именно в этой функции.
    if nrr > 200.0:
        st.warning(
            "NRR exceeds 200% — likely caused by limited prior-month data. "
            "Interpret with caution."
        )

    return nrr


# ---------------------------------------------------------------------------
# Блок 4 — Health (Section 6, Section 9)
# ---------------------------------------------------------------------------

def calculate_ltv(df: pd.DataFrame) -> float:
    """
    LTV = ARPU ÷ (churn_rate ÷ 100)
    Если churn_rate == 0 или None → ARPU × 36 (cap 36 месяцев). (Section 6)
    Кэшированный LTV НЕ использовать для unit economics или CAC payback.
    """
    arpu = calculate_arpu(df)
    churn_rate = calculate_churn_rate(df)

    if churn_rate is None or churn_rate == 0:
        return float(arpu * 36)

    return float(arpu / (churn_rate / 100))


def calculate_active_subscribers(df: pd.DataFrame) -> int:
    """
    Active Subscribers: количество уникальных customer_id со статусом
    'active' в last_month. (Section 6)
    """
    ctx = _compute_time_context(df)
    last_month = ctx["last_month"]
    if last_month is None:
        return 0

    # .assign() возвращает новый объект — нет side-effects (Section 17)
    data = df.assign(_period=df["date"].dt.to_period("M"))

    last_active = data[
        (data["status"] == "active") & (data["_period"] == last_month)
    ]
    return int(last_active["customer_id"].nunique())


def calculate_lost_subscribers(df: pd.DataFrame) -> int | None:
    """
    Lost Subscribers: уникальные customer_id активные в prev_month,
    но отсутствующие в active rows в last_month.
    Если prev_month_status != 'ok' → None. (Section 6)
    """
    ctx = _compute_time_context(df)
    if ctx["prev_month_status"] != "ok":
        return None

    prev_month = ctx["prev_month"]
    last_month = ctx["last_month"]

    active_prev = _get_active_customer_ids_for_period(df, prev_month)
    active_last = _get_active_customer_ids_for_period(df, last_month)

    lost = active_prev - active_last
    return int(len(lost))


def calculate_existing_subscribers(df: pd.DataFrame) -> int:
    """
    Existing Subscribers: уникальные customer_id активные И в prev_month,
    И в last_month. (Section 6)
    """
    ctx = _compute_time_context(df)
    if ctx["prev_month_status"] != "ok" or ctx["last_month"] is None:
        return 0

    prev_month = ctx["prev_month"]
    last_month = ctx["last_month"]

    active_prev = _get_active_customer_ids_for_period(df, prev_month)
    active_last = _get_active_customer_ids_for_period(df, last_month)

    return int(len(active_prev & active_last))


# ---------------------------------------------------------------------------
# Блок 5 — Cohort (Section 7, Section 9)
# ---------------------------------------------------------------------------

def calculate_cohort_table(df: pd.DataFrame) -> pd.DataFrame | None:
    """
    Когортная таблица удержания.

    Правила (Section 7):
    - Когортный период: первый calendar month с status=='active' AND amount > 0.
    - Минимум 3 различных когортных месяца → иначе None.
    - «Retained in month N»: customer_id имеет хотя бы одну строку
      status=='active' в этом календарном месяце (amount НЕ проверяем).
    - Ноль-amount активные строки считаются retained.
    - Намеренная асимметрия: когортный вход amount > 0,
      удержание только status=='active'. (Section 7: «Intentional asymmetry»)
    - Отображать max 12 последних когорт.
    - Retention % = retained_N ÷ cohort_size × 100.
    """
    # Строки для когортного входа: status=='active' AND amount > 0
    # .assign() вместо subscript-мутации — требование иммутабельности (Section 17)
    entry_data = (
        df[(df["status"] == "active") & (df["amount"] > 0)]
        .assign(_period=lambda x: x["date"].dt.to_period("M"))
    )

    if entry_data.empty:
        return None

    # Определяем когорту каждого клиента (первый месяц вхождения)
    cohort_map = (
        entry_data.groupby("customer_id")["_period"]
        .min()
        .rename("cohort")
    )

    # Минимум 3 различных когортных месяца — Section 7
    unique_cohorts = sorted(cohort_map.unique())
    if len(unique_cohorts) < 3:
        return None

    # Берём max 12 последних когорт — Section 7
    cohorts_to_show = unique_cohorts[-12:]

    # Строки для определения удержания: только status=='active' (amount не нужен)
    # .assign() вместо subscript-мутации — требование иммутабельности (Section 17)
    retention_data = (
        df[df["status"] == "active"]
        .assign(_period=lambda x: x["date"].dt.to_period("M"))
    )

    # Присоединяем когорту к retention_data
    retention_data = retention_data.join(cohort_map, on="customer_id", how="left")
    retention_data = retention_data[retention_data["cohort"].isin(cohorts_to_show)]

    # Определяем максимальный горизонт (разница в месяцах)
    max_horizon = 0
    for cohort in cohorts_to_show:
        later = [p for p in retention_data["_period"].unique() if p >= cohort]
        if later:
            horizon = (max(later) - cohort).n
            max_horizon = max(max_horizon, horizon)

    # Строим таблицу: строки — когорты, столбцы — month_0, month_1, ...
    records = []
    for cohort in cohorts_to_show:
        cohort_customers = set(cohort_map[cohort_map == cohort].index)
        cohort_size = len(cohort_customers)
        row = {"Cohort": str(cohort), "Size": cohort_size}

        for n in range(max_horizon + 1):
            target_period = cohort + n
            retained_in_n = retention_data[
                (retention_data["cohort"] == cohort)
                & (retention_data["_period"] == target_period)
            ]["customer_id"].nunique()

            retention_pct = round((retained_in_n / cohort_size) * 100, 1) if cohort_size > 0 else None
            col_name = f"Month {n}"
            row[col_name] = retention_pct

        records.append(row)

    result_df = pd.DataFrame(records).set_index("Cohort")
    return result_df


# ---------------------------------------------------------------------------
# Флаги качества данных
# Кэшируется через @st.cache_data — Section 9
# ---------------------------------------------------------------------------

@st.cache_data
def get_data_quality_flags(df_clean: pd.DataFrame) -> dict:
    """
    Возвращает флаги качества данных.
    Доступ только через session_state['data_quality_flags']['key'] —
    НЕ дублировать как top-level ключи. (Section 14)

    Ключи:
      prev_month_status      : 'ok' | 'missing' | 'gap'
      last_month_is_fallback : bool
      last_month_used        : str (YYYY-MM) или None
    """
    ctx = _compute_time_context(df_clean)

    last_month_used = (
        str(ctx["last_month"]) if ctx["last_month"] is not None else None
    )

    return {
        "prev_month_status": ctx["prev_month_status"],
        "last_month_is_fallback": ctx["last_month_is_fallback"],
        "last_month_used": last_month_used,
    }


# ---------------------------------------------------------------------------
# Бандл всех метрик
# Кэшируется через @st.cache_data — Section 9
# ТОЛЬКО эти две функции кэшируются. Отдельные метрики — нет.
# ---------------------------------------------------------------------------

@st.cache_data
def get_all_metrics(df_clean: pd.DataFrame) -> dict:
    """
    Возвращает словарь со всеми метриками для дашборда.
    Кэшируется через @st.cache_data — Section 9.
    calculate_reactivation_mrr и calculate_reactivated_subscribers
    принимают arpu как аргумент — передаём чтобы избежать повторного
    вычисления (Section 9: «arpu passed to avoid recomputation»).

    Возвращаемые ключи соответствуют Section 9 (все блоки 1–5).

    Дополнительно возвращает промежуточные значения для Excel-формул:
    - mrr_prev_month, active_subscribers_prev_month, expansion_mrr
    """
    # --- Блок 1: Revenue ---
    mrr = calculate_mrr(df_clean)
    arr = calculate_arr(df_clean)
    arpu = calculate_arpu(df_clean)
    total_revenue = calculate_total_revenue(df_clean)

    # --- Блок 2: Growth ---
    new_mrr = calculate_new_mrr(df_clean)
    reactivation_mrr = calculate_reactivation_mrr(df_clean, arpu)
    growth_rate = calculate_growth_rate(df_clean)
    new_subscribers = calculate_new_subscribers(df_clean)
    reactivated_subscribers = calculate_reactivated_subscribers(df_clean, arpu)

    # --- Блок 3: Retention ---
    churn_rate = calculate_churn_rate(df_clean)
    revenue_churn = calculate_revenue_churn(df_clean)
    nrr = calculate_nrr(df_clean)

    # --- Блок 4: Health ---
    ltv = calculate_ltv(df_clean)
    active_subscribers = calculate_active_subscribers(df_clean)
    lost_subscribers = calculate_lost_subscribers(df_clean)
    existing_subscribers = calculate_existing_subscribers(df_clean)

    # --- Блок 5: Cohort ---
    cohort_table = calculate_cohort_table(df_clean)

    # --- Промежуточные значения для Excel-формул ---
    ctx = _compute_time_context(df_clean)
    mrr_prev_month = None
    active_subscribers_prev_month = None
    expansion_mrr = None

    if ctx["prev_month_status"] == "ok":
        prev_month = ctx["prev_month"]
        active = (
            df_clean[(df_clean["status"] == "active") & (df_clean["amount"] > 0)]
            .assign(_period=lambda x: x["date"].dt.to_period("M"))
        )

        # MRR prev month
        rows_prev = active[active["_period"] == prev_month]
        if not rows_prev.empty:
            mrr_prev_month = float(rows_prev.groupby("customer_id")["amount"].sum().sum())

        # Active Subscribers prev month
        active_subscribers_prev_month = len(rows_prev["customer_id"].unique())

        # Expansion MRR (для NRR) — клиенты с ростом amount в last_month vs prev_month
        last_month = ctx["last_month"]
        rows_last = active[active["_period"] == last_month]

        if not rows_last.empty and not rows_prev.empty:
            prev_amounts = rows_prev.groupby("customer_id")["amount"].sum()
            last_amounts = rows_last.groupby("customer_id")["amount"].sum()
            common_customers = prev_amounts.index.intersection(last_amounts.index)

            expansion = 0.0
            for cid in common_customers:
                delta = last_amounts[cid] - prev_amounts[cid]
                if delta > 0:
                    expansion += delta
            expansion_mrr = float(expansion)

    return {
        # Блок 1 — Revenue
        "mrr": mrr,
        "arr": arr,
        "arpu": arpu,
        "total_revenue": total_revenue,
        # Блок 2 — Growth
        "new_mrr": new_mrr,
        "reactivation_mrr": reactivation_mrr,
        "growth_rate": growth_rate,
        "new_subscribers": new_subscribers,
        "reactivated_subscribers": reactivated_subscribers,
        # Блок 3 — Retention
        "churn_rate": churn_rate,
        "revenue_churn": revenue_churn,
        "nrr": nrr,
        # Блок 4 — Health
        "ltv": ltv,
        "active_subscribers": active_subscribers,
        "lost_subscribers": lost_subscribers,
        "existing_subscribers": existing_subscribers,
        # Блок 5 — Cohort
        "cohort_table": cohort_table,
        # Промежуточные значения для Excel-формул
        "mrr_prev_month": mrr_prev_month,
        "active_subscribers_prev_month": active_subscribers_prev_month,
        "expansion_mrr": expansion_mrr,
    }
