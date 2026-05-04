"""
app/pages/6_pricing.py
SubAudit — Страница сравнения тарифов и апгрейда.
Строго по Master Specification Sheet v2.9, Section 2, 4, 16 (Step 6).
"""

import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Конфигурация страницы
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SubAudit — Pricing",
    page_icon="💳",
    layout="wide",
)

# ─────────────────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────────────────────────────────────

def _get_current_plan() -> str:
    """
    Возвращает текущий план пользователя из session_state.
    Если пользователь не авторизован — возвращает 'free'.
    Section 14: user_plan хранится в session_state.
    """
    return st.session_state.get("user_plan", "free")


def _is_logged_in() -> bool:
    """
    Проверяет, авторизован ли пользователь.
    Section 14: user_email хранится в session_state.
    """
    return bool(st.session_state.get("user_email"))


def _render_subscription_warning() -> None:
    """
    Отображает предупреждение о проблеме с подпиской, если оно установлено.
    Section 13: subscription_warning + subscription_warning_reason.
    """
    if st.session_state.get("subscription_warning"):
        reason = st.session_state.get("subscription_warning_reason", "")
        if reason == "no_cache":
            # Section 13: HTTP 401 или ошибка без кэша
            st.warning(
                "⚠️ Не удалось проверить статус подписки. "
                "Отображается план по умолчанию. "
                "Payment processors may take up to 60 seconds. "
                "Please refresh in a moment."
            )
        elif reason == "api_error":
            # Section 13: ошибка API, используется кэш
            st.warning(
                "⚠️ Используются кэшированные данные подписки. "
                "Статус может быть неактуальным."
            )


# ─────────────────────────────────────────────────────────────────────────────
# Данные тарифных планов (Section 2 — Pricing Plans)
# ─────────────────────────────────────────────────────────────────────────────

# Структура тарифов строго по Section 2 таблице Feature / FREE / STARTER / PRO
PLANS: list[dict] = [
    {
        "id": "free",
        "name": "FREE",
        "price": "$0",
        "price_sub": "навсегда",
        "login_required": False,
        "max_rows": "1 000",
        "csv_per_session": "1",
        "metric_blocks": "Базовые (блоки 1–2)",
        "pdf_export": "С водяным знаком",
        "excel_export": "Нет",
        "forecast": "Нет",
        "simulation": "Нет",
        "cta_label": "Текущий план",
        "cta_disabled": True,
        "highlight": False,
    },
    {
        "id": "starter",
        "name": "STARTER",
        "price": "$19",
        "price_sub": "/ месяц",
        "login_required": True,
        "max_rows": "10 000",
        "csv_per_session": "1",
        "metric_blocks": "Все 5 блоков",
        "pdf_export": "Без водяного знака",
        "excel_export": "Да (с формулами)",
        "forecast": "Realistic ≥ 3 мес.; все сценарии ≥ 6 мес.",
        "simulation": "Нет",
        "cta_label": "Выбрать Starter",
        "cta_disabled": False,
        "highlight": False,
    },
    {
        "id": "pro",
        "name": "PRO",
        "price": "$49",
        "price_sub": "/ месяц",
        "login_required": True,
        "max_rows": "50 000",
        "csv_per_session": "1",
        "metric_blocks": "Все 5 блоков",
        "pdf_export": "Брендированный (название компании)",
        "excel_export": "Да (с формулами)",
        "forecast": "Как Starter",
        "simulation": "Дашборд + PDF экспорт",
        "cta_label": "Выбрать Pro",
        "cta_disabled": False,
        "highlight": True,  # PRO — выделенный план
    },
]

# Список строк таблицы сравнения (Section 2)
FEATURE_ROWS: list[tuple[str, str]] = [
    ("Авторизация", "login_required"),
    ("Макс. строк", "max_rows"),
    ("CSV файлов / сессию", "csv_per_session"),
    ("Блоки метрик", "metric_blocks"),
    ("PDF экспорт", "pdf_export"),
    ("Excel экспорт", "excel_export"),
    ("Прогноз", "forecast"),
    ("Симуляция", "simulation"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Рендер карточки тарифа
# ─────────────────────────────────────────────────────────────────────────────

def _render_plan_card(plan: dict, current_plan: str, is_logged_in: bool) -> None:
    """
    Рендерит карточку одного тарифа.
    CTA-кнопка ведёт на Lemon Squeezy (Section 13).
    Section 2: план FREE не требует авторизации, STARTER/PRO — требуют.
    """
    plan_id = plan["id"]
    is_current = (plan_id == current_plan)

    # Заголовок и цена
    if plan["highlight"]:
        st.markdown(f"### ⭐ {plan['name']}")
    else:
        st.markdown(f"### {plan['name']}")

    st.markdown(
        f"<span style='font-size:2rem;font-weight:700'>{plan['price']}</span>"
        f"<span style='color:gray'> {plan['price_sub']}</span>",
        unsafe_allow_html=True,
    )

    st.divider()

    # Список ключевых возможностей
    for label, key in FEATURE_ROWS:
        value = plan[key]
        # Булевые значения превращаем в читаемые строки
        if isinstance(value, bool):
            display = "✅ Да" if value else "❌ Нет"
        else:
            # «Нет» стилизуем серым
            if value == "Нет":
                display = f"<span style='color:gray'>—</span>"
            else:
                display = f"<strong>{value}</strong>"
        st.markdown(f"**{label}:** {display}", unsafe_allow_html=True)

    st.markdown("")  # отступ перед кнопкой

    # ── CTA-кнопка ──────────────────────────────────────────────────────────
    if is_current:
        # Текущий план — просто информационная плашка
        st.success("✅ Ваш текущий план")

    elif plan_id == "free":
        # FREE всегда доступен без действий
        if not is_logged_in:
            st.info("Вы используете бесплатный план")
        else:
            # Авторизованный пользователь с платным планом не может «даунгрейдиться»
            # здесь кнопка не нужна — downgrade описан как v1 limitation (Section 18)
            st.info("Бесплатный план доступен без подписки")

    else:
        # STARTER и PRO — кнопка ведёт на Lemon Squeezy (Section 13)
        # Lemon Squeezy не имеет webhook-интеграции (Section 13: «Webhooks — None»)
        # После оплаты пользователь возвращается на сайт и план обновляется на
        # Checkpoint 1 (login) или Checkpoint 2 (Dashboard load)
        if not is_logged_in:
            # Section 2: STARTER/PRO требуют авторизации
            st.button(
                f"🔐 Войдите, чтобы выбрать {plan['name']}",
                key=f"cta_{plan_id}_login",
                use_container_width=True,
                disabled=True,
            )
            st.caption("Авторизуйтесь через страницу Аккаунт для оформления подписки.")
        else:
            # Авторизован — показываем кнопку перехода на Lemon Squeezy
            # URL задаётся через st.secrets, здесь используется placeholder
            lemon_url = st.secrets.get(
                f"LEMON_SQUEEZY_CHECKOUT_{plan_id.upper()}",
                f"https://subaudit.lemonsqueezy.com/checkout/{plan_id}",
            )
            st.link_button(
                label=plan["cta_label"],
                url=lemon_url,
                use_container_width=True,
            )
            st.caption(
                "После оплаты вернитесь на сайт — план обновится автоматически."
            )


# ─────────────────────────────────────────────────────────────────────────────
# Основной рендер страницы
# ─────────────────────────────────────────────────────────────────────────────

def render_pricing_page() -> None:
    """
    Главная функция рендера страницы тарифов.
    Section 4: файл app/pages/6_pricing.py — план сравнения и CTA.
    Section 16 Step 6: эта страница входит в 6-й шаг разработки.
    """

    st.title("💳 Тарифные планы SubAudit")
    st.markdown(
        "Выберите план, который подходит для вашего бизнеса. "
        "Все данные обрабатываются **в памяти** и никогда не передаются третьим лицам."
    )

    # Получаем текущий план и статус авторизации
    current_plan = _get_current_plan()
    is_logged_in = _is_logged_in()

    # Предупреждение о проблеме с подпиской (Section 13)
    _render_subscription_warning()

    # Отображаем текущий план пользователя
    if is_logged_in:
        plan_display = current_plan.upper()
        st.info(f"🔑 Вы авторизованы. Текущий план: **{plan_display}**")
    else:
        st.info(
            "Вы не авторизованы. Используется бесплатный план. "
            "Для доступа к STARTER и PRO войдите через страницу **Аккаунт**."
        )

    st.markdown("---")

    # ── Карточки планов (Section 2) ──────────────────────────────────────────
    cols = st.columns(3, gap="medium")
    for col, plan in zip(cols, PLANS):
        with col:
            _render_plan_card(plan, current_plan, is_logged_in)

    st.markdown("---")

    # ── Детальная таблица сравнения (Section 2 — полная таблица) ────────────
    st.subheader("📊 Полное сравнение возможностей")

    # Строим таблицу через markdown для лучшей читаемости
    # Заголовок
    header = "| Возможность | FREE | STARTER ($19/мес) | PRO ($49/мес) |"
    divider = "|---|:---:|:---:|:---:|"

    rows = [header, divider]

    # Данные строк строго по Section 2
    table_data: list[tuple[str, str, str, str]] = [
        ("Авторизация",              "Нет",       "Да",       "Да"),
        ("Макс. строк",              "1 000",     "10 000",   "50 000"),
        ("CSV файлов / сессию",      "1",         "1",        "1"),
        ("Блоки метрик",             "Блоки 1–2", "Все 5",    "Все 5"),
        ("PDF экспорт",              "С водяным знаком", "Без водяного знака", "Брендированный"),
        ("Excel экспорт",            "—",         "✅ С формулами", "✅ С формулами"),
        ("Прогноз",                  "—",
         "Realistic ≥ 3 мес.; все сценарии ≥ 6 мес.",
         "Как Starter"),
        ("Симуляция",                "—",         "—",        "✅ Дашборд + PDF"),
    ]

    for feat, free_val, starter_val, pro_val in table_data:
        rows.append(f"| {feat} | {free_val} | {starter_val} | {pro_val} |")

    st.markdown("\n".join(rows))

    st.markdown("---")

    # ── FAQ / известные ограничения (Section 18) ────────────────────────────
    st.subheader("❓ Часто задаваемые вопросы")

    with st.expander("Что происходит при обновлении браузера?"):
        # Section 18: No persistent sessions across browser refresh
        st.markdown(
            "**Известное ограничение (v1):** Сессия не сохраняется между обновлениями браузера. "
            "При обновлении страницы потребуется повторная авторизация. "
            "Постоянные сессии запланированы в версии v3 (Supabase JWT cookies)."
        )

    with st.expander("Как быстро применяется смена тарифа?"):
        # Section 13: post-upgrade delay / Checkpoint логика
        st.markdown(
            "После оплаты через Lemon Squeezy вернитесь на сайт. "
            "Платёжные системы могут обрабатывать транзакцию **до 60 секунд**. "
            "Если план не обновился — подождите немного и обновите страницу. "
            "Статус проверяется автоматически при входе и загрузке дашборда."
        )

    with st.expander("Сохраняются ли мои данные на серверах SubAudit?"):
        # Section 3 (ℹ notice) — VERBATIM из спецификации
        st.info(
            "Files are processed in-memory and NEVER stored or sent to third parties."
        )

    with st.expander("Что такое 'даунгрейд' плана?"):
        # Section 18: Downgrade not detected mid-session
        st.markdown(
            "Понижение плана обнаруживается только при следующей загрузке дашборда "
            "в **новой сессии**. В рамках текущей сессии доступ сохраняется. "
            "Это принятое ограничение v1."
        )

    with st.expander("Чем отличается Симуляция на PRO?"):
        # Section 11: Simulation PRO only + ARPU homogeneity warning
        st.markdown(
            "Симуляция позволяет моделировать влияние изменения оттока, "
            "новых клиентов и повышения цены на MRR на 12 месяцев вперёд. "
            "\n\n"
            "⚠️ **Важно:** Результаты предполагают однородный ARPU. "
            "При смешанных тарифных уровнях реальное влияние на выручку "
            "может отличаться на 30–60%. Моделирование смешанных тарифов — "
            "в дорожной карте v2."
        )

    st.markdown("---")

    # ── Навигационные ссылки ─────────────────────────────────────────────────
    col_left, col_right = st.columns(2)
    with col_left:
        if st.button("← Вернуться к дашборду", use_container_width=True):
            st.switch_page("pages/5_dashboard.py")
    with col_right:
        if st.button("Перейти к аккаунту →", use_container_width=True):
            st.switch_page("pages/7_account.py")


# ─────────────────────────────────────────────────────────────────────────────
# Точка входа
# ─────────────────────────────────────────────────────────────────────────────

render_pricing_page()
