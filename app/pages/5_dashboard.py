"""
5_dashboard.py — Дашборд SubAudit
Строго по Master Specification Sheet v2.9, Section 16, Step 4.

Содержит:
  - Проверку сессии и плана (Section 2, 13, 14)
  - Все 5 блоков метрик (Section 6, 9)
  - Когортную таблицу (Section 7)
  - Прогноз HoltWinters (Section 10)
  - Симуляцию PRO-only (Section 11)
  - Экспорт PDF/Excel с ре-верификацией плана (Section 2, 13)
  - Флаги качества данных (Section 9, 14)
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import date

# ── Импорт внутренних модулей ──────────────────────────────────────────────────
from app.core.metrics import get_all_metrics, get_data_quality_flags
from app.core.forecast import generate_forecast
from app.core.simulation import run_simulation
from app.reports.pdf_builder import generate_pdf
from app.reports.excel_builder import generate_excel
from app.payments.lemon_squeezy import get_subscription_status
from app.observability.logger import log_error, log_warning, log_info

# Общие UI-утилиты: CSS скрытие авто-навигации + управляемый сайдбар
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from app.utils.page_setup import inject_nav_css, render_sidebar, record_activity

# ══════════════════════════════════════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ══════════════════════════════════════════════════════════════════════════════

def _fmt_currency(value: float | None, currency: str = "USD") -> str:
    """Форматирование числа как денежной суммы."""
    if value is None:
        return "N/A"
    return f"{currency} {value:,.2f}"


def _fmt_pct(value: float | None, decimals: int = 1) -> str:
    """Форматирование числа как процента."""
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}%"


def _fmt_int(value: int | None) -> str:
    """Форматирование целого числа."""
    if value is None:
        return "N/A"
    return f"{value:,}"


def _recheck_plan() -> str:
    """
    Ре-верификация плана у Lemon Squeezy — Section 13, Checkpoint 2.
    Вызывается при загрузке дашборда.
    Всегда показывает st.spinner (Section 13: «always st.spinner — never silent»).
    """
    user_email: str | None = st.session_state.get("user_email")
    with st.spinner("Verifying subscription..."):
        plan = get_subscription_status(user_email)
    st.session_state["user_plan"] = plan
    return plan


def _recheck_plan_for_export() -> str:
    """
    Ре-верификация плана перед любым экспортом — Section 13, Checkpoint 3.
    Section 2: «Plan MUST be re-verified from Lemon Squeezy BEFORE generating any PDF or Excel».
    """
    user_email: str | None = st.session_state.get("user_email")
    with st.spinner("Verifying subscription..."):
        plan = get_subscription_status(user_email)
    st.session_state["user_plan"] = plan
    return plan


# ══════════════════════════════════════════════════════════════════════════════
# БЛОКИ МЕТРИК
# ══════════════════════════════════════════════════════════════════════════════

def _render_block1_revenue(metrics: dict, currency: str) -> None:
    """
    Блок 1 — Revenue (Section 6, 9).
    Доступен для всех планов (FREE включён — Section 2, Metric blocks Basic).
    """
    st.subheader("💰 Revenue")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("MRR", _fmt_currency(metrics.get("mrr"), currency))
    with col2:
        st.metric("ARR", _fmt_currency(metrics.get("arr"), currency))
    with col3:
        st.metric("ARPU", _fmt_currency(metrics.get("arpu"), currency))
    with col4:
        st.metric("Total Revenue", _fmt_currency(metrics.get("total_revenue"), currency))


def _render_block2_growth(metrics: dict, currency: str) -> None:
    """
    Блок 2 — Growth (Section 6, 9).
    Доступен для всех планов (FREE включён — Section 2).
    growth_rate может быть None → показываем N/A (Section 6).
    """
    st.subheader("📈 Growth")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("New MRR", _fmt_currency(metrics.get("new_mrr"), currency))
    with col2:
        st.metric(
            "Reactivation MRR",
            _fmt_currency(metrics.get("reactivation_mrr"), currency),
        )
    with col3:
        growth = metrics.get("growth_rate")
        st.metric(
            "MoM Growth",
            _fmt_pct(growth),
            help="N/A when previous month data is unavailable or contains gaps (Section 6).",
        )
    with col4:
        st.metric("New Subscribers", _fmt_int(metrics.get("new_subscribers")))
    with col5:
        st.metric(
            "Reactivated Subscribers",
            _fmt_int(metrics.get("reactivated_subscribers")),
        )


def _render_block3_retention(metrics: dict, currency: str) -> None:
    """
    Блок 3 — Retention (Section 6, 9).
    Только Starter и PRO (Section 2).
    NRR > 200% → обязательное предупреждение (Section 6).
    """
    st.subheader("🔄 Retention")

    nrr = metrics.get("nrr")

    # NRR > 200% — предупреждение обязательно (Section 6)
    if nrr is not None and nrr > 200:
        st.warning(
            "NRR exceeds 200% — likely caused by limited prior-month data. "
            "Interpret with caution."
        )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "Churn Rate",
            _fmt_pct(metrics.get("churn_rate")),
            help="N/A when previous month data is unavailable (Section 6).",
        )
    with col2:
        st.metric(
            "Revenue Churn",
            _fmt_currency(metrics.get("revenue_churn"), currency),
            help="Four-scenario revenue churn (Section 8).",
        )
    with col3:
        st.metric(
            "NRR",
            _fmt_pct(nrr),
            help="Net Revenue Retention clamped 0–999% (Section 6).",
        )


def _render_block4_health(metrics: dict, currency: str) -> None:
    """
    Блок 4 — Health (Section 6, 9).
    Только Starter и PRO (Section 2).
    LTV cap = 36 мес. — подсказка обязательна (Section 6).
    """
    st.subheader("❤️ Health")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "LTV",
            _fmt_currency(metrics.get("ltv"), currency),
            # Подсказка обязательна (Section 6 LTV info box)
            help=(
                "LTV cap = 36 months (ARPU × 36). "
                "At 2–3% monthly churn, true LTV is 33–108% higher than the capped value. "
                "Do NOT use capped LTV for unit economics or CAC payback decisions."
            ),
        )
    with col2:
        st.metric(
            "Active Subscribers",
            _fmt_int(metrics.get("active_subscribers")),
        )
    with col3:
        st.metric(
            "Lost Subscribers",
            _fmt_int(metrics.get("lost_subscribers")),
            help="N/A when previous month data is unavailable (Section 6).",
        )
    with col4:
        st.metric(
            "Existing Subscribers",
            _fmt_int(metrics.get("existing_subscribers")),
        )


def _render_block5_cohort(metrics: dict) -> None:
    """
    Блок 5 — Cohort Table (Section 7, 9).
    Только Starter и PRO (Section 2).
    Требования: max 12 когорт, RdYlGn, st.dataframe() (Section 7).
    """
    st.subheader("🧩 Cohort Retention")

    cohort_df: pd.DataFrame | None = metrics.get("cohort_table")

    if cohort_df is None:
        # Section 7: требуется минимум 3 различных когортных месяца
        st.info(
            "At least 3 distinct cohort months are required to display the cohort table."
        )
        return

    # Section 7: max 12 самых свежих когорт
    if len(cohort_df) > 12:
        cohort_df = cohort_df.tail(12)

    # Section 7: st.dataframe() + background_gradient(colormap='RdYlGn')
    st.dataframe(
        cohort_df.style.background_gradient(cmap="RdYlGn", axis=None),
        use_container_width=True,
    )
    st.caption(
        "Retention %: retained_N ÷ cohort_size × 100. "
        "Zero-amount active rows count as retained (paused/discounted — not churn). Section 7."
    )


# ══════════════════════════════════════════════════════════════════════════════
# ПРОГНОЗ
# ══════════════════════════════════════════════════════════════════════════════

def _render_forecast(df: pd.DataFrame, plan: str, metrics: dict, currency: str) -> None:
    """
    Раздел прогноза (Section 10).
    Starter и PRO — гейтинг по количеству месяцев.
    """
    st.subheader("🔮 Revenue Forecast")

    # Гейтинг по плану (Section 2)
    if plan == "free":
        st.info("Upgrade to Starter or PRO to access forecast.")
        return

    forecast_result: dict | None = generate_forecast(df)

    # generate_forecast() возвращает None если данных < 3 мес. или ошибка HoltWinters
    if forecast_result is None:
        # Сообщения выводятся внутри generate_forecast() (Section 10)
        return

    data_months_used: int = forecast_result.get("data_months_used", 0)
    scenarios: dict = forecast_result.get("scenarios", {})
    months_labels: list = forecast_result.get("months_labels", [])

    # Сохраняем forecast_dict в session_state (Section 14)
    # Export gate: None когда data_months_used < 6 (Section 10)
    st.session_state["forecast_dict"] = forecast_result if data_months_used >= 6 else None

    # 3–5 месяцев — только Realistic, предупреждение ДО графика (Section 10)
    if data_months_used < 6:
        st.warning(
            f"Only {data_months_used} months of data available. "
            "Showing Realistic scenario only. "
            "At least 6 months required for Pessimistic/Optimistic scenarios and export."
        )

    # Строим Plotly-график
    fig = go.Figure()

    # Realistic — всегда показывается (Section 10)
    if "realistic" in scenarios:
        fig.add_trace(
            go.Scatter(
                x=months_labels,
                y=scenarios["realistic"],
                mode="lines+markers",
                name="Realistic",
                line=dict(color="#2563EB", width=2),
            )
        )

    # Pessimistic и Optimistic — только при ≥ 6 месяцах (Section 10)
    if data_months_used >= 6:
        if "pessimistic" in scenarios:
            fig.add_trace(
                go.Scatter(
                    x=months_labels,
                    y=scenarios["pessimistic"],
                    mode="lines",
                    name="Pessimistic",
                    line=dict(color="#DC2626", width=1.5, dash="dash"),
                )
            )
        if "optimistic" in scenarios:
            fig.add_trace(
                go.Scatter(
                    x=months_labels,
                    y=scenarios["optimistic"],
                    mode="lines",
                    name="Optimistic",
                    line=dict(color="#16A34A", width=1.5, dash="dash"),
                )
            )

    fig.update_layout(
        xaxis_title="Month",
        yaxis_title=f"MRR ({currency})",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=0, r=0, t=30, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Футер при data_months_used < 6 (Section 10: export gate footnote)
    if data_months_used < 6:
        st.caption(
            "Forecast omitted — fewer than 6 months of data available."
        )


# ══════════════════════════════════════════════════════════════════════════════
# СИМУЛЯЦИЯ (PRO only)
# ══════════════════════════════════════════════════════════════════════════════

def _render_simulation(df: pd.DataFrame, plan: str, metrics: dict, currency: str) -> None:
    """
    Раздел симуляции — только PRO (Section 11, Section 2).
    base_arpu == 0 guard обрабатывается внутри run_simulation() (Section 11).
    """
    st.subheader("🧪 Growth Simulation")

    # Гейтинг — только PRO (Section 2, 11)
    if plan != "pro":
        st.info("Upgrade to PRO to access the Growth Simulation dashboard.")
        return

    st.markdown("Adjust parameters to model the impact of growth levers on MRR.")

    # Подсказка об ограничении ARPU (Section 11 — обязательный tooltip)
    st.info(
        "⚠️ Results assume uniform ARPU. With mixed pricing tiers, "
        "actual revenue impact may differ by 30–60%. "
        "Mixed-tier modelling is v2 roadmap."
    )

    # Параметры симуляции (Section 11 Input Parameters)
    # Слайдеры показывают пользователю проценты (целые числа) для удобства.
    # Значения делятся на 100 перед передачей в run_simulation(),
    # чтобы соответствовать спецификации: churn_reduction 0.0–1.0, price_increase −0.5–5.0.
    col1, col2, col3 = st.columns(3)
    with col1:
        churn_reduction_pct = st.slider(
            "Churn Reduction",
            min_value=0,
            max_value=100,
            value=20,
            step=5,
            format="%d%%",
            help="Fractional reduction in churn rate (20% = 0.20 less churn). Section 11.",
        )
        churn_reduction = churn_reduction_pct / 100  # 0.0–1.0 согласно Section 11
    with col2:
        new_customers_month = st.number_input(
            "New Customers / Month",
            min_value=0,
            max_value=10_000,
            value=50,
            step=10,
            help="Additional new customers per month. Section 11.",
        )
    with col3:
        price_increase_pct = st.slider(
            "Price Increase",
            min_value=-50,
            max_value=500,
            value=0,
            step=5,
            format="%d%%",
            help="Fractional ARPU change (10% = 0.10 increase). Section 11.",
        )
        price_increase = price_increase_pct / 100  # −0.5–5.0 согласно Section 11

    # Запуск симуляции
    sim_result: dict | None = run_simulation(
        df=df,
        churn_reduction=churn_reduction,
        new_customers_month=int(new_customers_month),
        price_increase=price_increase,
    )

    # Сохраняем simulation_dict в session_state (Section 14)
    st.session_state["simulation_dict"] = sim_result

    # run_simulation() вернёт None при base_arpu==0 — и покажет st.warning() (Section 11)
    if sim_result is None:
        return

    # Отображение результатов симуляции
    mrr_change_pct = sim_result.get("mrr_change_pct")  # None когда base_mrr == 0 (Section 11)

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric(
            "Projected MRR (12mo)",
            _fmt_currency(sim_result.get("projected_mrr_12"), currency),
            delta=f"{mrr_change_pct:.1f}%" if mrr_change_pct is not None else "N/A",
        )
    with col_b:
        st.metric(
            "Projected Subscribers (12mo)",
            _fmt_int(sim_result.get("projected_subscribers_12")),
        )
    with col_c:
        st.metric(
            "New Churn Rate",
            _fmt_pct(sim_result.get("new_churn_rate")),
        )

    # График MRR по месяцам симуляции
    monthly_mrr: list | None = sim_result.get("monthly_mrr")
    if monthly_mrr:
        months = list(range(1, len(monthly_mrr) + 1))
        fig_sim = go.Figure(
            go.Scatter(
                x=months,
                y=monthly_mrr,
                mode="lines+markers",
                name="Simulated MRR",
                line=dict(color="#7C3AED", width=2),
                fill="tozeroy",
                fillcolor="rgba(124, 58, 237, 0.08)",
            )
        )
        fig_sim.update_layout(
            xaxis_title="Month",
            yaxis_title=f"MRR ({currency})",
            margin=dict(l=0, r=0, t=30, b=0),
        )
        st.plotly_chart(fig_sim, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# ЭКСПОРТ
# ══════════════════════════════════════════════════════════════════════════════

def _render_export(df: pd.DataFrame, plan: str, metrics: dict, currency: str) -> None:
    """
    Экспорт PDF и Excel (Section 2, 5, 13).
    Перед любым экспортом ОБЯЗАТЕЛЬНА ре-верификация плана (Section 2, 13 Checkpoint 3).
    Debounce через pdf_generating / excel_generating (Section 14).
    """
    st.subheader("📥 Export")

    forecast_dict = st.session_state.get("forecast_dict")
    simulation_dict = st.session_state.get("simulation_dict")
    company_name: dict = st.session_state.get("company_name", {
        "display_name": "",
        "filename_safe_name": "report",
    })

    col_pdf, col_excel = st.columns(2)

    # ── PDF ──────────────────────────────────────────────────────────────────
    with col_pdf:
        st.markdown("**PDF Report**")

        if plan == "free":
            st.caption("Free plan: PDF exported with watermark.")
        elif plan == "starter":
            st.caption("Starter plan: PDF without watermark.")
        else:
            st.caption("PRO plan: Branded PDF with company name.")

        if st.button("Generate PDF", disabled=st.session_state.get("pdf_generating", False)):
            # Debounce guard (Section 14)
            st.session_state["pdf_generating"] = True
            try:
                # Checkpoint 3 — ре-верификация плана (Section 13, Section 2)
                export_plan = _recheck_plan_for_export()

                pdf_bytes: bytes = generate_pdf(
                    df=df,
                    metrics=metrics,
                    forecast_dict=forecast_dict,
                    simulation_dict=simulation_dict,
                    plan=export_plan,
                    currency=currency,
                    company_name=company_name,
                )
                filename = f"{company_name.get('filename_safe_name', 'report')}_subaudit.pdf"
                st.download_button(
                    label="⬇️ Download PDF",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                )
                log_info(f"PDF exported. plan={export_plan}")
            except Exception as exc:
                log_error(str(exc), exc=exc, context="pdf_export")
                st.error("PDF generation failed. Please try again.")
            finally:
                st.session_state["pdf_generating"] = False

    # ── Excel ────────────────────────────────────────────────────────────────
    with col_excel:
        st.markdown("**Excel Export**")

        # Только Starter и PRO (Section 2)
        if plan == "free":
            st.info("Upgrade to Starter or PRO for Excel export with formulas.")
        else:
            st.caption("Excel with formulas included.")

            if st.button(
                "Generate Excel",
                disabled=st.session_state.get("excel_generating", False),
            ):
                # Debounce guard (Section 14)
                st.session_state["excel_generating"] = True
                try:
                    # Checkpoint 3 — ре-верификация плана (Section 13, Section 2)
                    export_plan = _recheck_plan_for_export()

                    if export_plan == "free":
                        st.warning(
                            "Your subscription was downgraded. Excel export requires Starter or PRO."
                        )
                    else:
                        excel_bytes: bytes = generate_excel(
                            df=df,
                            metrics=metrics,
                            forecast_dict=forecast_dict,
                            simulation_dict=simulation_dict,
                            plan=export_plan,
                            currency=currency,
                            company_name=company_name,
                        )
                        filename_xl = (
                            f"{company_name.get('filename_safe_name', 'report')}_subaudit.xlsx"
                        )
                        st.download_button(
                            label="⬇️ Download Excel",
                            data=excel_bytes,
                            file_name=filename_xl,
                            mime=(
                                "application/vnd.openxmlformats-officedocument"
                                ".spreadsheetml.sheet"
                            ),
                        )
                        log_info(f"Excel exported. plan={export_plan}")
                except Exception as exc:
                    log_error(exc, context="excel_export")
                    st.error("Excel generation failed. Please try again.")
                finally:
                    st.session_state["excel_generating"] = False


# ══════════════════════════════════════════════════════════════════════════════
# ПРЕДУПРЕЖДЕНИЕ О ПОДПИСКЕ
# ══════════════════════════════════════════════════════════════════════════════

def _render_subscription_warning() -> None:
    """
    Отображение предупреждения о проблемах с верификацией подписки (Section 13).
    Post-upgrade delay message (Section 13).
    """
    if not st.session_state.get("subscription_warning", False):
        return

    reason = st.session_state.get("subscription_warning_reason", "")
    if reason == "no_cache":
        st.warning(
            "Subscription could not be verified. Showing Free plan features. "
            "Payment processors may take up to 60 seconds. Please refresh in a moment."
        )
    elif reason == "api_error":
        st.warning(
            "Subscription API error — using cached plan. "
            "If this persists, please contact support."
        )


# ══════════════════════════════════════════════════════════════════════════════
# ФЛАГИ КАЧЕСТВА ДАННЫХ
# ══════════════════════════════════════════════════════════════════════════════

def _render_data_quality_warnings(flags: dict) -> None:
    """
    Отображение предупреждений о качестве данных (Section 9, 14, Section 5).
    flags: {prev_month_status, last_month_is_fallback, last_month_used}
    """
    if flags.get("last_month_is_fallback"):
        st.warning(
            f"⚠️ Last month fallback active: {flags.get('last_month_used')}. "
            "Fewer than 5 unique active customers in the most recent month. "
            "Some metrics (Churn Rate, Growth Rate, NRR) may not be available. "
            "(Section 5 — 'last month' definition)"
        )

    prev_status = flags.get("prev_month_status")
    if prev_status == "gap":
        st.warning(
            "⚠️ Gap detected in monthly data: previous calendar month has no data. "
            "Growth Rate, Churn Rate, NRR, and Lost Subscribers show N/A. "
            "(Section 5 — 'prev month' definition)"
        )
    elif prev_status == "missing":
        st.warning(
            "⚠️ Previous month data is missing. "
            "Growth Rate, Churn Rate, NRR, and Lost Subscribers show N/A."
        )


# ══════════════════════════════════════════════════════════════════════════════
# ГЛАВНАЯ ФУНКЦИЯ СТРАНИЦЫ
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """
    Точка входа 5_dashboard.py.
    Порядок действий:
      1. Проверка session_state (наличие df_clean, column_mapping) (Section 14)
      2. Ре-верификация плана — Checkpoint 2 (Section 13)
      3. Вычисление метрик через get_all_metrics() и get_data_quality_flags() (Section 9)
      4. Отображение предупреждений о качестве данных (Section 5, 9)
      5. Рендер блоков метрик 1–5 в зависимости от плана (Section 2, 9)
      6. Прогноз (Section 10)
      7. Симуляция — PRO only (Section 11)
      8. Экспорт (Section 2, 13)
    """
    st.set_page_config(
        page_title="Dashboard — SubAudit",
        page_icon="📊",  # отсутствовал — добавлен для консистентности со всеми страницами
        layout="wide",
    )

    # Скрываем автонавигацию Streamlit, показываем управляемый сайдбар
    inject_nav_css()
    render_sidebar()
    st.title("📊 SubAudit Dashboard")

    # ── Проверка наличия данных в сессии ─────────────────────────────────────
    # Section 14: df_clean должен быть в session_state
    if "df_clean" not in st.session_state or st.session_state["df_clean"] is None:
        st.warning(
            "No data loaded. Please upload a CSV file first.",
            icon="⚠️",
        )
        st.page_link("pages/2_upload.py", label="Go to Upload", icon="📂")
        return

    if "column_mapping" not in st.session_state:
        st.warning("Column mapping not found. Please complete the mapping step.")
        st.page_link("pages/3_mapping.py", label="Go to Mapping", icon="🗂️")
        return

    df: pd.DataFrame = st.session_state["df_clean"]
    currency: str = st.session_state.get("currency", "USD")

    # ── Checkpoint 2 — ре-верификация плана при загрузке дашборда ────────────
    # Section 13: «On Dashboard load (5_dashboard.py)»
    plan: str = _recheck_plan()

    # ── Предупреждение о подписке ─────────────────────────────────────────────
    _render_subscription_warning()

    # ── Вычисление метрик ─────────────────────────────────────────────────────
    # Section 9: get_all_metrics и get_data_quality_flags кешируются @st.cache_data
    try:
        metrics: dict = get_all_metrics(df)
        flags: dict = get_data_quality_flags(df)
    except Exception as exc:
        log_error(exc, context="dashboard_metrics")
        st.error("Failed to compute metrics. Please re-upload your file.")
        return

    # Сохраняем в session_state (Section 14)
    st.session_state["metrics_dict"] = metrics
    st.session_state["data_quality_flags"] = flags

    # ── Флаги качества данных ─────────────────────────────────────────────────
    _render_data_quality_warnings(flags)

    # ── Блоки метрик ──────────────────────────────────────────────────────────
    # Section 2: FREE — Blocks 1–2; Starter/PRO — All 5 blocks
    _render_block1_revenue(metrics, currency)
    st.divider()

    _render_block2_growth(metrics, currency)
    st.divider()

    if plan in ("starter", "pro"):
        _render_block3_retention(metrics, currency)
        st.divider()

        _render_block4_health(metrics, currency)
        st.divider()

        _render_block5_cohort(metrics)
        st.divider()
    else:
        # FREE — показываем CTA для апгрейда
        st.info(
            "🔒 Retention, Health and Cohort metrics are available on Starter and PRO plans.",
        )
        st.page_link("pages/6_pricing.py", label="View Pricing", icon="💎")
        st.divider()

    # ── Прогноз ───────────────────────────────────────────────────────────────
    # Section 10: Starter и PRO только; FREE — заглушка
    _render_forecast(df, plan, metrics, currency)
    st.divider()

    # ── Симуляция ─────────────────────────────────────────────────────────────
    # Section 11: только PRO
    _render_simulation(df, plan, metrics, currency)
    st.divider()

    # ── Экспорт ───────────────────────────────────────────────────────────────
    # Section 2, 13
    _render_export(df, plan, metrics, currency)


# ── Запуск страницы ───────────────────────────────────────────────────────────
# Streamlit запускает страницу как скрипт — main() вызывается напрямую.
# "or True" убран намеренно: он вызывал main() при любом импорте модуля (баг).
main()
