"""
app/pages/1_landing.py
Маркетинговая (лендинговая) страница SubAudit.

Спецификация: Section 4 (File Structure), Section 16 (Development Order, Step 1),
Section 2 (Pricing Plans).

Раздел 4: "Landing / marketing page"
Раздел 16, шаг 1: "main.py + 1_landing.py + 2_upload.py"
"""

import streamlit as st

# ---------------------------------------------------------------------------
# Конфигурация страницы
# Section 4: 1_landing.py — точка входа для маркетинговой страницы
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SubAudit — Subscription Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Глобальные стили — кастомный CSS для полноценного маркетингового лендинга
# Применяем refined, editorial эстетику: тёмный фон, акцент #4F8EF7, типографика
# ---------------------------------------------------------------------------
CUSTOM_CSS = """
<style>
/* --- Импорт шрифтов --- */
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap');

/* --- Сброс и базовые переменные --- */
:root {
    --bg-primary:   #0D1117;
    --bg-card:      #161B22;
    --bg-card-alt:  #1C2333;
    --accent:       #4F8EF7;
    --accent-soft:  rgba(79, 142, 247, 0.12);
    --accent-glow:  rgba(79, 142, 247, 0.30);
    --text-primary: #E6EDF3;
    --text-muted:   #8B949E;
    --text-caption: #6E7681;
    --border:       rgba(255, 255, 255, 0.08);
    --border-accent:rgba(79, 142, 247, 0.35);
    --success:      #3FB950;
    --warning:      #D29922;
    --radius:       12px;
    --radius-lg:    20px;
}

/* --- Скрываем стандартный Streamlit chrome --- */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 0 !important; max-width: 100% !important; }

/* Скрываем весь сайдбар и кнопку-гамбургер ► (без этого кнопка видна даже при collapsed) */
[data-testid="stSidebar"]         { display: none !important; }
[data-testid="collapsedControl"]   { display: none !important; }
[data-testid="stSidebarNav"]       { display: none !important; }

/* --- Базовый фон --- */
.stApp {
    background: var(--bg-primary) !important;
    font-family: 'DM Sans', sans-serif;
    color: var(--text-primary);
}

/* --- HERO секция --- */
.hero-section {
    background: radial-gradient(ellipse 80% 50% at 50% -20%,
                rgba(79, 142, 247, 0.18) 0%, transparent 65%),
                var(--bg-primary);
    padding: 96px 5% 80px;
    text-align: center;
    border-bottom: 1px solid var(--border);
    position: relative;
    overflow: hidden;
}
.hero-section::before {
    content: '';
    position: absolute;
    inset: 0;
    background:
        repeating-linear-gradient(
            90deg,
            transparent,
            transparent 79px,
            rgba(255,255,255,0.022) 80px
        ),
        repeating-linear-gradient(
            0deg,
            transparent,
            transparent 79px,
            rgba(255,255,255,0.022) 80px
        );
    pointer-events: none;
}
.hero-badge {
    display: inline-block;
    background: var(--accent-soft);
    border: 1px solid var(--border-accent);
    color: var(--accent);
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 5px 14px;
    border-radius: 100px;
    margin-bottom: 24px;
}
.hero-title {
    font-family: 'DM Serif Display', serif;
    font-size: clamp(40px, 5vw, 72px);
    font-weight: 400;
    color: var(--text-primary);
    line-height: 1.12;
    margin: 0 0 20px;
    letter-spacing: -0.02em;
}
.hero-title em {
    font-style: italic;
    color: var(--accent);
}
.hero-subtitle {
    font-size: clamp(16px, 1.8vw, 20px);
    color: var(--text-muted);
    max-width: 560px;
    margin: 0 auto 40px;
    line-height: 1.65;
    font-weight: 300;
}
.hero-cta-row {
    display: flex;
    gap: 14px;
    justify-content: center;
    flex-wrap: wrap;
    margin-bottom: 56px;
}
.btn-primary {
    display: inline-block;
    background: var(--accent);
    color: #fff !important;
    font-weight: 600;
    font-size: 15px;
    padding: 13px 28px;
    border-radius: 8px;
    text-decoration: none !important;
    transition: filter 0.18s, transform 0.18s;
    cursor: pointer;
    border: none;
    letter-spacing: 0.01em;
}
.btn-primary:hover { filter: brightness(1.12); transform: translateY(-1px); }
.btn-secondary {
    display: inline-block;
    background: transparent;
    color: var(--text-primary) !important;
    font-weight: 500;
    font-size: 15px;
    padding: 12px 28px;
    border-radius: 8px;
    border: 1px solid var(--border);
    text-decoration: none !important;
    transition: border-color 0.18s, background 0.18s;
    cursor: pointer;
}
.btn-secondary:hover {
    border-color: var(--accent);
    background: var(--accent-soft);
}

/* --- Статистика Hero --- */
.hero-stats {
    display: flex;
    justify-content: center;
    gap: 48px;
    flex-wrap: wrap;
    padding-top: 40px;
    border-top: 1px solid var(--border);
}
.stat-item { text-align: center; }
.stat-number {
    font-family: 'DM Serif Display', serif;
    font-size: 36px;
    color: var(--text-primary);
    line-height: 1.1;
}
.stat-label {
    font-size: 13px;
    color: var(--text-muted);
    margin-top: 4px;
}

/* --- Секция Features --- */
.section {
    padding: 80px 5%;
    max-width: 1200px;
    margin: 0 auto;
}
.section-tag {
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 12px;
}
.section-title {
    font-family: 'DM Serif Display', serif;
    font-size: clamp(28px, 3vw, 44px);
    font-weight: 400;
    color: var(--text-primary);
    line-height: 1.18;
    margin: 0 0 14px;
    letter-spacing: -0.02em;
}
.section-body {
    font-size: 16px;
    color: var(--text-muted);
    max-width: 560px;
    line-height: 1.7;
    font-weight: 300;
    margin-bottom: 48px;
}

/* --- Feature cards сетка --- */
.feature-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 20px;
}
.feature-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 28px;
    transition: border-color 0.2s, box-shadow 0.2s;
}
.feature-card:hover {
    border-color: var(--border-accent);
    box-shadow: 0 0 24px var(--accent-glow);
}
.feature-icon {
    font-size: 28px;
    margin-bottom: 16px;
    display: block;
}
.feature-name {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 8px;
}
.feature-desc {
    font-size: 14px;
    color: var(--text-muted);
    line-height: 1.65;
}

/* --- Divider --- */
.divider {
    border: none;
    border-top: 1px solid var(--border);
    margin: 0;
}

/* --- Pricing Cards (Section 2) --- */
.pricing-wrapper {
    background: var(--bg-card);
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    padding: 80px 5%;
}
.pricing-inner { max-width: 1200px; margin: 0 auto; }
.pricing-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 20px;
    margin-top: 48px;
}
.pricing-card {
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 32px;
    position: relative;
    transition: transform 0.2s;
}
.pricing-card:hover { transform: translateY(-3px); }
.pricing-card.featured {
    border-color: var(--accent);
    box-shadow: 0 0 40px var(--accent-glow);
}
.pricing-badge {
    position: absolute;
    top: -13px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--accent);
    color: #fff;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 4px 14px;
    border-radius: 100px;
    white-space: nowrap;
}
.plan-name {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 12px;
}
.plan-price {
    font-family: 'DM Serif Display', serif;
    font-size: 48px;
    color: var(--text-primary);
    line-height: 1;
    margin-bottom: 4px;
}
.plan-price sub {
    font-family: 'DM Sans', sans-serif;
    font-size: 16px;
    font-weight: 400;
    color: var(--text-muted);
    vertical-align: baseline;
}
.plan-tagline {
    font-size: 14px;
    color: var(--text-muted);
    margin-bottom: 28px;
    line-height: 1.5;
}
.plan-features {
    list-style: none;
    padding: 0;
    margin: 0 0 32px;
    border-top: 1px solid var(--border);
    padding-top: 24px;
}
.plan-features li {
    font-size: 14px;
    color: var(--text-muted);
    padding: 7px 0;
    display: flex;
    align-items: flex-start;
    gap: 10px;
    line-height: 1.5;
}
.plan-features li .check {
    color: var(--success);
    font-size: 14px;
    flex-shrink: 0;
    margin-top: 1px;
}
.plan-features li .cross {
    color: var(--text-caption);
    flex-shrink: 0;
    margin-top: 1px;
}
.plan-cta {
    display: block;
    text-align: center;
    padding: 12px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    text-decoration: none !important;
    cursor: pointer;
    transition: all 0.18s;
}
.plan-cta.primary {
    background: var(--accent);
    color: #fff !important;
}
.plan-cta.primary:hover { filter: brightness(1.1); }
.plan-cta.outline {
    border: 1px solid var(--border);
    color: var(--text-primary) !important;
}
.plan-cta.outline:hover {
    border-color: var(--accent);
    background: var(--accent-soft);
}

/* --- Notice privacy --- */
.privacy-notice {
    background: var(--accent-soft);
    border: 1px solid var(--border-accent);
    border-radius: var(--radius);
    padding: 16px 22px;
    display: flex;
    align-items: flex-start;
    gap: 12px;
    margin-top: 40px;
    font-size: 14px;
    color: var(--text-muted);
    line-height: 1.6;
}
.privacy-notice .icon { font-size: 18px; flex-shrink: 0; }

/* --- Security/Trust bar --- */
.trust-bar {
    background: var(--bg-card-alt);
    border-top: 1px solid var(--border);
    padding: 32px 5%;
    text-align: center;
}
.trust-bar-inner {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 40px;
    flex-wrap: wrap;
    max-width: 900px;
    margin: 0 auto;
}
.trust-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--text-muted);
    font-weight: 500;
}
.trust-item .ti { font-size: 16px; }

/* --- Footer --- */
.landing-footer {
    background: var(--bg-primary);
    border-top: 1px solid var(--border);
    padding: 32px 5%;
    text-align: center;
    font-size: 13px;
    color: var(--text-caption);
}

/* --- Streamlit кнопки переопределение --- */
div[data-testid="stButton"] > button {
    background: var(--accent) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-family: 'DM Sans', sans-serif !important;
    padding: 10px 24px !important;
    font-size: 15px !important;
    transition: filter 0.18s !important;
    width: 100%;
}
div[data-testid="stButton"] > button:hover {
    filter: brightness(1.12) !important;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# HERO секция
# Section 16 Step 1: 1_landing.py — маркетинговая страница
# ---------------------------------------------------------------------------
st.markdown("""
<div class="hero-section">
    <div class="hero-badge">📊 Subscription Analytics — Powered by your own CSV</div>
    <h1 class="hero-title">
        Turn your subscription data<br>into <em>clear, actionable</em> insights
    </h1>
    <p class="hero-subtitle">
        Upload your CSV once. Get MRR, churn, NRR, LTV, cohort analysis,
        forecasts and scenario simulations — in under 60 seconds.
        No SQL. No dashboards. No setup.
    </p>
    <div class="hero-cta-row">
        <a class="btn-primary" href="/upload" target="_self">
            → &nbsp;Analyse my data — it's free
        </a>
        <a class="btn-secondary" href="#pricing">
            View pricing
        </a>
    </div>
    <div class="hero-stats">
        <div class="stat-item">
            <div class="stat-number">15+</div>
            <div class="stat-label">SaaS metrics calculated</div>
        </div>
        <div class="stat-item">
            <div class="stat-number">&lt; 60s</div>
            <div class="stat-label">From upload to insight</div>
        </div>
        <div class="stat-item">
            <div class="stat-number">50 k</div>
            <div class="stat-label">Max rows (Pro plan)</div>
        </div>
        <div class="stat-item">
            <div class="stat-number">0</div>
            <div class="stat-label">Files stored or shared</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Секция: Возможности продукта
# Section 6 (Metric Formulas), Section 7 (Cohort), Section 10 (Forecast),
# Section 11 (Simulation) — маркетинговое представление функций
# ---------------------------------------------------------------------------
st.markdown("""
<div class="section">
    <div class="section-tag">Everything you need</div>
    <h2 class="section-title">Five metric blocks,<br>one CSV upload</h2>
    <p class="section-body">
        SubAudit computes every metric a SaaS founder or analyst needs —
        from basic MRR to forward-looking simulations — automatically,
        using your subscription export.
    </p>
    <div class="feature-grid">
        <div class="feature-card">
            <span class="feature-icon">💰</span>
            <div class="feature-name">Block 1 — Revenue</div>
            <div class="feature-desc">
                MRR, ARR, ARPU and Total Revenue. Multi-row customers
                summed correctly. Currency-consistent by design.
            </div>
        </div>
        <div class="feature-card">
            <span class="feature-icon">📈</span>
            <div class="feature-name">Block 2 — Growth</div>
            <div class="feature-desc">
                New MRR, Reactivation MRR, Growth Rate, New Subscribers.
                Reactivated customers tracked separately from new — no metric inflation.
            </div>
        </div>
        <div class="feature-card">
            <span class="feature-icon">🔄</span>
            <div class="feature-name">Block 3 — Retention</div>
            <div class="feature-desc">
                Churn Rate, Revenue Churn (4 distinct scenarios),
                and NRR clamped to 0–999% with data-quality warnings.
            </div>
        </div>
        <div class="feature-card">
            <span class="feature-icon">❤️</span>
            <div class="feature-name">Block 4 — Health</div>
            <div class="feature-desc">
                LTV (36-month cap, zero-churn aware), Active Subscribers,
                Lost Subscribers, Existing Subscribers.
            </div>
        </div>
        <div class="feature-card">
            <span class="feature-icon">🗂️</span>
            <div class="feature-name">Block 5 — Cohort Analysis</div>
            <div class="feature-desc">
                Up to 12 rolling monthly cohorts with RdYlGn heatmap.
                Correct SaaS semantics: paused accounts count as retained.
            </div>
        </div>
        <div class="feature-card">
            <span class="feature-icon">🔮</span>
            <div class="feature-name">Forecast & Simulation</div>
            <div class="feature-desc">
                Holt-Winters 12-month forecast with pessimistic / realistic /
                optimistic scenarios. PRO: churn-reduction &amp; price-increase simulator.
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Секция: Приватность и безопасность файлов
# Section 3 (ℹ notice): "Files are processed in-memory and NEVER stored
#   or sent to third parties." — обязательная формулировка на Upload page,
#   здесь дополнительно используется в маркетинговом контексте
# ---------------------------------------------------------------------------
st.markdown("""
<div class="section">
    <div class="section-tag">Privacy first</div>
    <h2 class="section-title">Your data never<br>leaves your browser session</h2>
    <p class="section-body">
        SubAudit is built on a strict in-memory processing model.
        No file is written to disk, cached in a database, or forwarded
        to any third-party service.
    </p>
    <div class="privacy-notice">
        <span class="icon">ℹ️</span>
        <span>
            <strong style="color: #E6EDF3;">Files are processed in-memory and NEVER stored
            or sent to third parties.</strong><br>
            Your subscription data is yours alone. The moment you close your browser
            session, all data is gone.
        </span>
    </div>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Секция: Ценообразование
# Section 2 — Pricing Plans: FREE / STARTER $19/mo / PRO $49/mo
# Все значения таблицы взяты строго из спецификации (Section 2)
# ---------------------------------------------------------------------------
st.markdown('<div id="pricing"></div>', unsafe_allow_html=True)
st.markdown("""
<div class="pricing-wrapper">
<div class="pricing-inner">
    <div class="section-tag" style="text-align:center;">Pricing</div>
    <h2 class="section-title" style="text-align:center; max-width:none;">
        Start free. Upgrade when you need more.
    </h2>
    <p class="section-body" style="margin: 0 auto 0; text-align:center;">
        No credit card required on the Free plan.
        All paid plans billed monthly via Lemon Squeezy.
    </p>

    <div class="pricing-grid">

        <!-- FREE -->
        <div class="pricing-card">
            <div class="plan-name">Free</div>
            <div class="plan-price">$0<sub>/mo</sub></div>
            <div class="plan-tagline">No login required. Get started instantly.</div>
            <ul class="plan-features">
                <li><span class="check">✓</span> Up to 1,000 rows</li>
                <li><span class="check">✓</span> 1 CSV file per session</li>
                <li><span class="check">✓</span> Metric Blocks 1 &amp; 2 (Revenue + Growth)</li>
                <li><span class="check">✓</span> PDF export with watermark</li>
                <li><span class="cross">–</span> Blocks 3–5 (Retention, Health, Cohort)</li>
                <li><span class="cross">–</span> Excel export</li>
                <li><span class="cross">–</span> Forecast</li>
                <li><span class="cross">–</span> Simulation</li>
            </ul>
            <a class="plan-cta outline" href="/upload" target="_self">
                Start for free →
            </a>
        </div>

        <!-- STARTER — featured -->
        <div class="pricing-card featured">
            <div class="pricing-badge">Most popular</div>
            <div class="plan-name">Starter</div>
            <div class="plan-price">$19<sub>/mo</sub></div>
            <div class="plan-tagline">For growing SaaS teams tracking monthly performance.</div>
            <ul class="plan-features">
                <li><span class="check">✓</span> Up to 10,000 rows</li>
                <li><span class="check">✓</span> 1 CSV file per session</li>
                <li><span class="check">✓</span> All 5 metric blocks</li>
                <li><span class="check">✓</span> PDF export — no watermark</li>
                <li><span class="check">✓</span> Excel export with formulas</li>
                <li><span class="check">✓</span> Forecast: realistic ≥ 3 mo; all 3 scenarios ≥ 6 mo</li>
                <li><span class="cross">–</span> Simulation dashboard</li>
            </ul>
            <a class="plan-cta primary" href="/pricing" target="_self">
                Get Starter →
            </a>
        </div>

        <!-- PRO -->
        <div class="pricing-card">
            <div class="plan-name">Pro</div>
            <div class="plan-price">$49<sub>/mo</sub></div>
            <div class="plan-tagline">For established teams running scenario planning.</div>
            <ul class="plan-features">
                <li><span class="check">✓</span> Up to 50,000 rows</li>
                <li><span class="check">✓</span> 1 CSV file per session</li>
                <li><span class="check">✓</span> All 5 metric blocks</li>
                <li><span class="check">✓</span> PDF export — branded (company name)</li>
                <li><span class="check">✓</span> Excel export with formulas</li>
                <li><span class="check">✓</span> Forecast: all 3 scenarios ≥ 6 mo</li>
                <li><span class="check">✓</span> <strong>Simulation dashboard + PDF export</strong></li>
            </ul>
            <a class="plan-cta outline" href="/pricing" target="_self">
                Get Pro →
            </a>
        </div>

    </div>
</div>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Trust bar — краткие сигналы доверия
# ---------------------------------------------------------------------------
st.markdown("""
<div class="trust-bar">
    <div class="trust-bar-inner">
        <span class="trust-item"><span class="ti">🔒</span> In-memory processing only</span>
        <span class="trust-item"><span class="ti">📋</span> CSV — no integrations required</span>
        <span class="trust-item"><span class="ti">⚡</span> Powered by HoltWinters + pandas</span>
        <span class="trust-item"><span class="ti">🐍</span> Python 3.11 · Streamlit Cloud</span>
        <span class="trust-item"><span class="ti">💳</span> Payments via Lemon Squeezy</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# CTA-секция перед footer
# Кнопка Streamlit для навигации на страницу загрузки (2_upload.py)
# Section 16 Step 1: 2_upload.py создаётся в том же шаге разработки
# ---------------------------------------------------------------------------
st.markdown("<div style='height: 64px;'></div>", unsafe_allow_html=True)

col_l, col_c, col_r = st.columns([2, 3, 2])
with col_c:
    st.markdown("""
    <div style="text-align:center; margin-bottom: 16px;">
        <div class="section-tag">Ready to start?</div>
        <h2 class="section-title" style="font-size: clamp(24px, 3vw, 36px);">
            Upload your CSV and<br>get metrics in under a minute
        </h2>
        <p style="color: var(--text-muted); font-size: 15px; margin-bottom: 28px; font-weight: 300;">
            Free plan — no account, no credit card.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Streamlit-кнопка: навигация на страницу загрузки
    if st.button("→  Analyse my subscription data  —  it's free", key="cta_upload_bottom"):
        # Section 4: 2_upload.py — страница загрузки CSV
        st.switch_page("pages/2_upload.py")

st.markdown("<div style='height: 48px;'></div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("""
<div class="landing-footer">
    <strong style="color: #8B949E;">SubAudit</strong>
    &nbsp;·&nbsp;
    Subscription analytics for SaaS founders
    &nbsp;·&nbsp;
    <a href="/upload" target="_self" style="color: #4F8EF7; text-decoration:none;">Get started</a>
    &nbsp;·&nbsp;
    <a href="/pricing" target="_self" style="color: #4F8EF7; text-decoration:none;">Pricing</a>
    &nbsp;·&nbsp;
    <a href="/account" target="_self" style="color: #4F8EF7; text-decoration:none;">Account</a>
    <br><br>
    <span style="font-size: 12px;">
        Files are processed in-memory and NEVER stored or sent to third parties.
    </span>
</div>
""", unsafe_allow_html=True)
