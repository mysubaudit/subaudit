"""
app/pages/1_landing.py
Маркетинговая (лендинговая) страница SubAudit.
Spec v2.9 — Section 4, 16, 2

CHANGELOG:
- #pricing якоря → /pricing (реальная страница)
- Nav "Pricing" → /pricing
- Footer "Pricing" → /pricing  
- Hero "View pricing" → /pricing
- Account кнопка в nav bar
"""

import streamlit as st

st.set_page_config(
    page_title="SubAudit — Subscription Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap');

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

#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 0 !important; max-width: 100% !important; }
[data-testid="stSidebar"]        { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
[data-testid="stSidebarNav"]     { display: none !important; }

.stApp {
    background: var(--bg-primary) !important;
    font-family: 'DM Sans', sans-serif;
    color: var(--text-primary);
}

/* ── TOP NAV ── */
.top-nav {
    position: sticky;
    top: 0;
    z-index: 999;
    background: rgba(13, 17, 23, 0.92);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border);
    padding: 0 5%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 60px;
}
.nav-logo {
    font-family: 'DM Serif Display', serif;
    font-size: 20px;
    color: var(--text-primary);
    text-decoration: none !important;
    letter-spacing: -0.01em;
}
.nav-logo span { color: var(--accent); }
.nav-links {
    display: flex;
    align-items: center;
    gap: 4px;
}
.nav-link {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-muted) !important;
    text-decoration: none !important;
    padding: 6px 14px;
    border-radius: 6px;
    transition: color 0.15s, background 0.15s;
}
.nav-link:hover {
    color: var(--text-primary) !important;
    background: rgba(255,255,255,0.05);
}
.nav-btn {
    font-size: 13px;
    font-weight: 600;
    color: var(--accent) !important;
    text-decoration: none !important;
    padding: 7px 16px;
    border-radius: 6px;
    border: 1px solid var(--border-accent);
    background: var(--accent-soft);
    transition: background 0.15s, filter 0.15s;
    margin-left: 8px;
}
.nav-btn:hover {
    background: rgba(79, 142, 247, 0.22);
    filter: brightness(1.1);
}
.nav-btn-primary {
    font-size: 13px;
    font-weight: 600;
    color: #fff !important;
    text-decoration: none !important;
    padding: 7px 16px;
    border-radius: 6px;
    background: var(--accent);
    border: 1px solid transparent;
    transition: filter 0.15s;
    margin-left: 4px;
}
.nav-btn-primary:hover { filter: brightness(1.12); }

/* ── HERO ── */
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
        repeating-linear-gradient(90deg, transparent, transparent 79px,
            rgba(255,255,255,0.022) 80px),
        repeating-linear-gradient(0deg, transparent, transparent 79px,
            rgba(255,255,255,0.022) 80px);
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
.hero-title em { font-style: italic; color: var(--accent); }
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
}
.btn-secondary:hover { border-color: var(--accent); background: var(--accent-soft); }

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
.stat-label { font-size: 13px; color: var(--text-muted); margin-top: 4px; }

/* ── SECTIONS ── */
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

/* ── FEATURE GRID ── */
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
.feature-icon { font-size: 28px; margin-bottom: 16px; display: block; }
.feature-name { font-size: 16px; font-weight: 600; color: var(--text-primary); margin-bottom: 8px; }
.feature-desc { font-size: 14px; color: var(--text-muted); line-height: 1.65; }

.divider { border: none; border-top: 1px solid var(--border); margin: 0; }

/* ── PRICING ── */
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
.plan-tagline { font-size: 14px; color: var(--text-muted); margin-bottom: 28px; line-height: 1.5; }
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
.plan-features li .check { color: var(--success); font-size: 14px; flex-shrink: 0; margin-top: 1px; }
.plan-features li .cross { color: var(--text-caption); flex-shrink: 0; margin-top: 1px; }
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
.plan-cta.primary { background: var(--accent); color: #fff !important; }
.plan-cta.primary:hover { filter: brightness(1.1); }
.plan-cta.outline { border: 1px solid var(--border); color: var(--text-primary) !important; }
.plan-cta.outline:hover { border-color: var(--accent); background: var(--accent-soft); }

/* ── PRIVACY ── */
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

/* ── TRUST BAR ── */
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

/* ── FOOTER ── */
.landing-footer {
    background: var(--bg-primary);
    border-top: 1px solid var(--border);
    padding: 32px 5%;
    text-align: center;
    font-size: 13px;
    color: var(--text-caption);
}

/* ── STREAMLIT BUTTON ── */
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
div[data-testid="stButton"] > button:hover { filter: brightness(1.12) !important; }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ── NAV ──────────────────────────────────────────────────────────────────────
# Проблема 3: Account кнопка в шапке
# Все ссылки ведут на реальные страницы, НЕТ якорей #pricing
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<nav class="top-nav">
    <a class="nav-logo" href="/" target="_self">Sub<span>Audit</span></a>
    <div class="nav-links">
        <a class="nav-link" href="/upload"  target="_self">Upload</a>
        <a class="nav-link" href="/pricing" target="_self">Pricing</a>
        <a class="nav-btn"  href="/account" target="_self">⚙ Account</a>
        <a class="nav-btn-primary" href="/upload" target="_self">Get started →</a>
    </div>
</nav>
""", unsafe_allow_html=True)

# ── HERO ─────────────────────────────────────────────────────────────────────
# FIX: "View pricing" → /pricing (не #pricing)
# ─────────────────────────────────────────────────────────────────────────────
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
        <a class="btn-secondary" href="/pricing" target="_self">
            View pricing ↓
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

# ── FEATURES ──────────────────────────────────────────────────────────────────
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
                Reactivated customers tracked separately — no metric inflation.
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
                Paused accounts count as retained — correct SaaS semantics.
            </div>
        </div>
        <div class="feature-card">
            <span class="feature-icon">🔮</span>
            <div class="feature-name">Forecast &amp; Simulation</div>
            <div class="feature-desc">
                Holt-Winters 12-month forecast with pessimistic / realistic /
                optimistic scenarios. PRO: churn-reduction &amp; price-increase simulator.
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# ── PRIVACY ───────────────────────────────────────────────────────────────────
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

# ── PRICING PREVIEW ───────────────────────────────────────────────────────────
# Секция pricing на лендинге — краткий preview с CTA на /pricing
# Карточки здесь показывают ключевые отличия, детали — на /pricing
# ─────────────────────────────────────────────────────────────────────────────
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

        <!-- STARTER -->
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

    <!-- CTA под карточками -->
    <div style="text-align:center; margin-top: 40px;">
        <a class="btn-secondary" href="/pricing" target="_self"
           style="display:inline-block; padding: 12px 32px;">
            See full pricing details →
        </a>
    </div>

</div>
</div>
""", unsafe_allow_html=True)

# ── TRUST BAR ─────────────────────────────────────────────────────────────────
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

# ── CTA BOTTOM ────────────────────────────────────────────────────────────────
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

    if st.button("→  Analyse my subscription data  —  it's free", key="cta_upload_bottom"):
        st.switch_page("pages/2_upload.py")

st.markdown("<div style='height: 48px;'></div>", unsafe_allow_html=True)

# ── LEGAL SECTION ─────────────────────────────────────────────────────────────
# Terms of Service, Privacy Policy, Refund Policy
# Требование Lemon Squeezy — обязательные документы на лендинге
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="section" style="padding-top: 48px; padding-bottom: 16px;">
    <div style="text-align:center; margin-bottom: 24px;">
        <span style="color: var(--text-caption); font-size: 13px; letter-spacing: 0.06em; text-transform: uppercase;">Legal</span>
    </div>
    <div style="display:flex; justify-content:center; gap: 24px; flex-wrap:wrap;">
        <a href="#terms-of-service"   style="color: var(--accent); font-size: 14px; text-decoration:none;">Terms of Service</a>
        <span style="color: var(--text-caption);">·</span>
        <a href="#privacy-policy"     style="color: var(--accent); font-size: 14px; text-decoration:none;">Privacy Policy</a>
        <span style="color: var(--text-caption);">·</span>
        <a href="#refund-policy"      style="color: var(--accent); font-size: 14px; text-decoration:none;">Refund Policy</a>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Terms of Service ──────────────────────────────────────────────────────────
with st.expander("📄 Terms of Service", expanded=False):
    st.markdown("""
<div id="terms-of-service"></div>

**Terms of Service**

*Last updated: May 8, 2025*

**1. Acceptance of Terms**

By accessing or using SubAudit ("the Service"), you agree to be bound by these Terms of Service. If you do not agree, do not use the Service.

**2. Description of Service**

SubAudit is a web-based SaaS analytics tool that allows users to upload CSV files containing subscription data and receive computed metrics, forecasts, and exportable reports (PDF and Excel).

**3. User Accounts**

Access to paid features requires authentication via a magic link sent to your email address. You are responsible for maintaining the security of your email account. Sessions are not persistent across browser refreshes — this is a known limitation of the current version.

**4. Subscription Plans and Billing**

- **Free** plan: available without registration, limited to 1,000 rows per session.
- **Starter** ($19/month) and **Pro** ($49/month) plans are billed as monthly recurring subscriptions through Lemon Squeezy.
- Subscriptions renew automatically on the same day each month unless cancelled before the renewal date.
- Plan features are enforced at the time of export. Downgrade mid-session may not be reflected until the next login.

**5. Data Processing**

All uploaded files are processed entirely in-memory within your browser session. No file is written to disk, stored in a database, or forwarded to any third-party service. All data is discarded when the session ends. See our Privacy Policy for full details.

**6. Acceptable Use**

You agree not to:
- Upload data you do not have the legal right to process.
- Attempt to reverse-engineer, scrape, or abuse the Service.
- Use the Service to process data containing personal information of individuals without appropriate legal basis.

**7. Intellectual Property**

All software, design, and analytics logic of SubAudit are the intellectual property of the developer. You may not copy, redistribute, or resell the Service.

**8. Limitation of Liability**

SubAudit is provided "as is" without warranties of any kind, express or implied. Metrics and forecasts are mathematical computations based on your uploaded data. We are not responsible for business decisions made on the basis of these outputs. In no event shall SubAudit be liable for any indirect, incidental, special, or consequential damages.

**9. Changes to Terms**

We reserve the right to update these Terms at any time. Continued use of the Service after changes constitutes your acceptance of the updated Terms.

**10. Governing Law**

These Terms are governed by applicable international commercial law. Disputes shall be resolved through good-faith negotiation before any formal proceedings.

**11. Contact**

For questions regarding these Terms, contact us at: **biz.sardorbek@gmail.com**
""", unsafe_allow_html=True)

# ── Privacy Policy ────────────────────────────────────────────────────────────
with st.expander("🔒 Privacy Policy", expanded=False):
    st.markdown("""
<div id="privacy-policy"></div>

**Privacy Policy**

*Last updated: May 8, 2025*

**1. What We Collect**

| Data | Why | Where stored |
|------|-----|--------------|
| Email address | Authentication via magic link | Supabase (auth only) |
| Subscription plan | Feature gating | Supabase + session memory |
| Company name (optional) | PDF branding for Pro users | Session memory only — never persisted |
| Error events | Bug tracking and stability | Sentry (anonymised) |

We do **not** collect names, phone numbers, payment card numbers, or any data from your uploaded CSV files.

**2. Your CSV Data**

Uploaded files are processed **entirely in-memory** within your active browser session. No file content is written to disk, stored in our database, or transmitted to any third party. Data is permanently discarded when your session ends. This is a core architectural guarantee, not a policy promise.

**3. Authentication**

We use Supabase to manage user accounts. When you request a magic link, your email address is stored in Supabase solely for authentication purposes. We do not store passwords.

**4. Payments**

Payments are handled by **Lemon Squeezy**. SubAudit never processes or stores payment card information. Lemon Squeezy's Privacy Policy applies to all payment transactions.

**5. Error Tracking**

We use **Sentry** for error monitoring. Events are anonymised — personally identifiable information (PII) is scrubbed before transmission. Sentry receives only error type, stack trace, and plan tier.

**6. Cookies and Tracking**

SubAudit does not use advertising cookies or tracking pixels. Streamlit Community Cloud may set technical session cookies required for the application to function.

**7. Data Retention**

- Email addresses: retained in Supabase until you request deletion.
- Error events: retained by Sentry for 30 days.
- CSV data: zero retention — discarded at session end.

**8. Your Rights**

You may request deletion of your account and email address at any time by contacting us. We will action deletion requests within 14 business days.

**9. Third-Party Services**

| Service | Purpose | Privacy Policy |
|---------|---------|----------------|
| Supabase | Authentication & database | supabase.com/privacy |
| Lemon Squeezy | Payments & subscriptions | lemonsqueezy.com/privacy |
| Sentry | Error monitoring | sentry.io/privacy |
| Streamlit Community Cloud | Application hosting | streamlit.io/privacy |

**10. Contact**

For privacy-related requests or questions: **biz.sardorbek@gmail.com**
""", unsafe_allow_html=True)

# ── Refund Policy ─────────────────────────────────────────────────────────────
with st.expander("💳 Refund Policy", expanded=False):
    st.markdown("""
<div id="refund-policy"></div>

**Refund Policy**

*Last updated: May 8, 2025*

**Our Commitment**

We want you to be satisfied with SubAudit. If the Service does not meet your expectations, we offer a straightforward refund process.

**7-Day Money-Back Guarantee**

If you are not satisfied with your Starter or Pro subscription, you may request a full refund within **7 days** of your initial purchase. No questions asked.

To request a refund, email us at **biz.sardorbek@gmail.com** with:
- The email address used to purchase
- Your Lemon Squeezy order number (found in your purchase confirmation email)

We will process your refund within **5 business days**. Refunds are issued to the original payment method.

**Renewals**

Refunds are not available for renewal charges after the 7-day window has passed. To avoid being charged for a renewal, cancel your subscription at least 24 hours before the next billing date via your Account page.

**Free Plan**

The Free plan is available at no charge and is not subject to any refund terms.

**Exceptions**

We reserve the right to refuse refunds in cases of:
- Abuse of the refund policy (multiple refund requests from the same user)
- Violation of the Terms of Service

**Contact**

For all refund requests: **biz.sardorbek@gmail.com**

Response time: within 2 business days.
""", unsafe_allow_html=True)

st.markdown("<div style='height: 32px;'></div>", unsafe_allow_html=True)

# ── FOOTER ────────────────────────────────────────────────────────────────────
# FIX: "Pricing" → /pricing (не #pricing)
# Обновлён: добавлены ссылки на юридические страницы
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="landing-footer">
    <strong style="color: #8B949E;">SubAudit</strong>
    &nbsp;·&nbsp;
    Subscription analytics for SaaS founders
    &nbsp;·&nbsp;
    <a href="/upload"   target="_self" style="color: #4F8EF7; text-decoration:none;">Get started</a>
    &nbsp;·&nbsp;
    <a href="/pricing"  target="_self" style="color: #4F8EF7; text-decoration:none;">Pricing</a>
    &nbsp;·&nbsp;
    <a href="/account"  target="_self" style="color: #4F8EF7; text-decoration:none;">Account</a>
    <br><br>
    <span style="font-size: 12px; color: var(--text-caption);">
        <a href="#terms-of-service" style="color: #6E7681; text-decoration:none;">Terms of Service</a>
        &nbsp;·&nbsp;
        <a href="#privacy-policy"   style="color: #6E7681; text-decoration:none;">Privacy Policy</a>
        &nbsp;·&nbsp;
        <a href="#refund-policy"    style="color: #6E7681; text-decoration:none;">Refund Policy</a>
    </span>
    <br><br>
    <span style="font-size: 12px;">
        Files are processed in-memory and NEVER stored or sent to third parties.
    </span>
</div>
""", unsafe_allow_html=True)