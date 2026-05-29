import streamlit as st
import pandas as pd
from io import StringIO

st.set_page_config(page_title="Help & Guide", page_icon="❓", layout="wide")

# Скрываем автонавигацию Streamlit, показываем управляемый сайдбар
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from app.utils.page_setup import inject_nav_css, render_sidebar
inject_nav_css()
render_sidebar()

# Back to landing link
st.caption(
    '<a href="/" target="_self" style="color: #4F8EF7; text-decoration: none; font-size: 14px;">← Back to Landing</a>',
    unsafe_allow_html=True,
)

st.title("❓ Help & User Guide")

# Quick navigation tabs
tab1, tab2, tab3, tab4 = st.tabs(["🚀 Quick Start", "📁 CSV Format", "📈 Metrics", "❓ FAQ"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: QUICK START
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    st.header("🚀 Quick Start Guide")

    st.markdown("""
    Get insights from your subscription data in 3 simple steps:

    **Step 1: Upload Your Data** 📤
    - Go to the **Upload** page
    - Upload your CSV file with subscription data
    - Supported formats: CSV files with customer transactions
    - Maximum file size: **15 MB**
    - Processing time: ~5-30 seconds depending on file size

    **Step 2: Map Your Columns** 🗺️
    - SubAudit will automatically detect your column names (Stripe, Paddle, Gumroad, LemonSqueezy, Chargebee)
    - Confirm or adjust the mapping — or skip this step entirely if your format is recognized
    - Required fields: **Customer ID**, **Date**, **Amount**, **Status**
    - Optional: **Currency**

    **Step 3: View Your Dashboard** 📊
    - Navigate to **Dashboard** to see:
      - Key metrics (MRR, ARR, ARPU, Churn Rate, NRR, LTV)
      - Revenue forecast (Starter and Pro plans)
      - Cohort retention analysis
      - Growth simulation (Pro plan only)
    - Export reports as PDF or Excel
    """)

    st.info("💡 **Tip:** Start with at least 3 months of historical data for accurate metrics and forecasts. 6+ months recommended for forecasts with all scenarios.")

    st.divider()

    st.subheader("📥 Download Sample CSV")
    st.markdown("Not sure about the format? Download our sample file to see the expected structure.")

    sample_data = {
        "customer_id": ["C001", "C001", "C001", "C002", "C002", "C003"],
        "date": ["2024-01-01", "2024-02-01", "2024-03-01", "2024-01-01", "2024-02-01", "2024-01-01"],
        "amount": [100.00, 100.00, 100.00, 50.00, 50.00, 200.00],
        "status": ["active", "active", "active", "active", "churned", "active"],
        "currency": ["USD", "USD", "USD", "USD", "USD", "USD"]
    }
    sample_df = pd.DataFrame(sample_data)
    csv_buffer = StringIO()
    sample_df.to_csv(csv_buffer, index=False)

    st.download_button(
        label="⬇️ Download sample_subscription_data.csv",
        data=csv_buffer.getvalue(),
        file_name="sample_subscription_data.csv",
        mime="text/csv"
    )

    st.divider()

    st.subheader("💳 Subscription Plans at a Glance")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### 🆓 Free — $0/mo")
        st.markdown("""
        - **1,000 rows** per session
        - Revenue & Growth metrics (Blocks 1–2)
        - PDF export with watermark
        - No Excel, no Forecast, no Simulation
        """)
    with col2:
        st.markdown("### ⭐ Starter — $9/mo")
        st.markdown("""
        - **10,000 rows** per session
        - All 5 metric blocks
        - PDF export without watermark
        - Excel export with formulas
        - Revenue forecast (3+ months)
        """)
    with col3:
        st.markdown("### 🚀 Pro — $19/mo")
        st.markdown("""
        - **50,000 rows** per session
        - Everything in Starter
        - **Growth Simulation** dashboard
        - Branded PDF with your company name
        """)

    st.markdown("""
    [View full pricing details →](/6_pricing)
    """)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: CSV FORMAT
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.header("📁 CSV File Requirements")

    st.markdown("""
    ### Required Columns

    Your CSV file must contain these **4 columns** (names can vary — SubAudit uses fuzzy matching):

    | Column | Description | Example Values |
    |--------|-------------|----------------|
    | **Customer ID** | Unique identifier for each customer | `C001`, `user_123`, `cust-456` |
    | **Date** | Billing or transaction date (YYYY-MM or YYYY-MM-DD) | `2024-01-01`, `2024-01` |
    | **Amount** | Subscription amount in one currency | `99.99`, `1000.00` |
    | **Status** | Subscription status | `active`, `churned`, `trial`, `past_due`, `cancelled` |

    ### Optional Column

    | Column | Description | Example Values |
    |--------|-------------|----------------|
    | **Currency** | Currency code | `USD`, `EUR`, `GBP` |

    ⚠️ **Important:**
    - SubAudit supports **single currency** only. If your file contains multiple currencies, the upload will be rejected.
    - **Date format**: use `YYYY-MM` or `YYYY-MM-DD`. Other formats may not be parsed correctly.
    - **Status values**: lowercase preferred. SubAudit normalizes: `Active` → `active`, `CANCELLED` → `cancelled`.
    """)

    st.divider()

    st.subheader("✅ DO and ❌ DON'T")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        **DO:**
        - ✅ Include at least 3 months of data (6+ recommended)
        - ✅ Use consistent date format (YYYY-MM or YYYY-MM-DD)
        - ✅ Include all customer transactions (one row per billing event)
        - ✅ Use lowercase status values (or let SubAudit normalize them)
        - ✅ Remove exact duplicate rows before upload (SubAudit also removes them automatically)
        """)

    with col2:
        st.markdown("""
        **DON'T:**
        - ❌ Mix multiple currencies in one file
        - ❌ Upload aggregated/summary data — use raw transactions
        - ❌ Upload files larger than **15 MB**
        - ❌ Upload more than your plan's row limit
        - ❌ Use Excel (.xlsx) files — use **CSV only**
        """)

    st.divider()

    st.subheader("🔍 Auto-Detected Formats")

    st.markdown("""
    SubAudit automatically recognizes these billing platforms — mapping is applied automatically:

    | Platform | Badge | Notes |
    |---------|-------|-------|
    | **Stripe** | 🎯 Stripe Detected | Export from Stripe Dashboard → Revenue |
    | **Paddle** | 🎯 Paddle Detected | Subscriptions → Export CSV |
    | **Gumroad** | 🎯 Gumroad Detected | Sales → Export CSV |
    | **LemonSqueezy** | 🎯 LemonSqueezy Detected | Orders → Export |
    | **Chargebee** | 🎯 Chargebee Detected | Subscriptions → Export |
    | **Other / Manual** | — | Use fuzzy matching to map columns |
    """)

    st.info("💡 If your format is recognized, column mapping is applied automatically. You can review and adjust it on the next step.")

    st.divider()

    st.subheader("🔧 What Happens During Upload?")

    st.markdown("""
    1. **Encoding Detection**: SubAudit automatically detects UTF-8, Windows-1251, Latin-1
    2. **Duplicate Removal**: Exact duplicate rows are identified and removed
    3. **Status Normalization**: Status values are converted to lowercase
    4. **Data Quality Check**:
       - Rows with amount = 0 are excluded from MRR
       - Rows with negative amounts are treated as refunds
       - Missing previous month data is flagged
    5. **Snapshot Save**: If you are signed in, your metrics are saved for month-over-month comparison

    You'll see a detailed cleaning report on the **Data Cleaning** page.
    """)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3: METRICS
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.header("📈 Metrics Explained")

    metrics_tab1, metrics_tab2, metrics_tab3, metrics_tab4, metrics_tab5, metrics_tab6, metrics_tab7 = st.tabs([
        "💰 MRR", "📊 ARR", "👤 ARPU", "📉 Churn Rate", "🔄 NRR", "💎 LTV", "🧩 Cohort"
    ])

    with metrics_tab1:
        st.subheader("💰 MRR (Monthly Recurring Revenue)")
        st.markdown("""
        **What it is:**
        Total recurring revenue from active subscriptions in the most recent month.

        **Formula:**
        `MRR = Sum of all amounts where status = 'active' in the latest month`

        **Why it matters:**
        MRR is the heartbeat of your subscription business. It shows your current revenue run rate.

        **What's a good MRR?**
        - Growing month-over-month = healthy business
        - Flat MRR = need to focus on acquisition or expansion
        - Declining MRR = churn problem or market saturation

        **Note:**
        - Rows with amount = 0 are excluded from MRR
        - Negative amounts (refunds) are excluded
        """)

    with metrics_tab2:
        st.subheader("📊 ARR (Annual Recurring Revenue)")
        st.markdown("""
        **What it is:**
        Your MRR projected over 12 months.

        **Formula:**
        `ARR = MRR × 12`

        **Why it matters:**
        ARR is the standard metric for B2B SaaS valuation and investor discussions.

        **Typical benchmarks:**
        - $120K ARR = ~$10K MRR — seed stage milestone
        - $1M ARR = ~$83K MRR — Series A milestone
        - $10M ARR = ~$833K MRR — late-stage growth
        """)

    with metrics_tab3:
        st.subheader("👤 ARPU (Average Revenue Per User)")
        st.markdown("""
        **What it is:**
        Average revenue per active subscriber in the most recent month.

        **Formula:**
        `ARPU = MRR / Active Subscribers`

        **Why it matters:**
        ARPU shows your pricing power and customer value. Higher ARPU = more revenue per customer.

        **How to improve ARPU:**
        - Upsell to higher tiers
        - Add premium features
        - Implement usage-based pricing
        """)

    with metrics_tab4:
        st.subheader("📉 Churn Rate")
        st.markdown("""
        **What it is:**
        Percentage of customers who cancelled their subscription in the most recent month.

        **Formula:**
        `Churn Rate = (Churned Subscribers / Active Subscribers Previous Month) × 100%`

        **Why it matters:**
        Churn is the silent killer of SaaS businesses. Even 5% monthly churn compounds to 46% annual churn.

        **Benchmarks:**
        - **Excellent**: < 3% monthly (< 30% annual)
        - **Good**: 3–5% monthly (30–50% annual)
        - **Needs improvement**: 5–7% monthly (50–60% annual)
        - **Critical**: > 7% monthly (> 60% annual)

        **Voluntary vs. Involuntary Churn:**
        SubAudit splits churn into two types:

        - **Voluntary Churn** (👍): Customers who actively cancel (status = `cancelled`). These customers made a conscious decision to leave.
        - **Involuntary Churn** (💳): Customers lost due to payment failures (status = `past_due`, `payment_failed`). Their payment method expired or was declined.

        **Why this split matters:**
        - High **voluntary** churn → focus on product improvements, pricing, or customer success
        - High **involuntary** churn → focus on payment recovery (dunning emails, card updater services)
        - Fixing involuntary churn is typically faster and cheaper than reducing voluntary churn
        """)

    with metrics_tab5:
        st.subheader("🔄 NRR (Net Revenue Retention)")
        st.markdown("""
        **What it is:**
        Percentage of revenue retained from existing customers, including expansions and contractions.

        **Formula:**
        `NRR = ((MRR_current - New_MRR + Reactivation_MRR) / MRR_previous) × 100%`

        **Why it matters:**
        NRR > 100% means you're growing revenue from existing customers even without new signups.

        **Benchmarks:**
        - **World-class**: > 120%
        - **Excellent**: 110–120%
        - **Good**: 100–110%
        - **Needs improvement**: 90–100%
        - **Critical**: < 90%

        **⚠️ Warning:**
        If NRR > 200%, it usually indicates limited previous month data. This is common in early-stage datasets.

        **Reactivation:**
        - Reactivation = customer returns after 2–9 months absence
        - Annual subscriptions (amount > 6× ARPU) are excluded from reactivation
        """)

    with metrics_tab6:
        st.subheader("💎 LTV (Lifetime Value)")
        st.markdown("""
        **What it is:**
        Expected total revenue from a customer over their entire subscription lifetime.

        **Formula:**
        `LTV = ARPU / Churn Rate`

        **Special case:**
        If Churn Rate = 0%, we cap LTV at `ARPU × 36 months` to avoid infinity.

        **Why it matters:**
        LTV helps you determine how much you can spend on customer acquisition (CAC).
        Rule of thumb: `LTV / CAC > 3` is healthy.

        **⚠️ Known Limitation:**
        LTV is capped at 36 months. Do NOT use this for unit economics or CAC payback calculations
        if your actual customer lifetime exceeds 3 years.
        """)

    with metrics_tab7:
        st.subheader("🧩 Cohort Retention Analysis")
        st.markdown("""
        **What it is:**
        Tracks how many customers from each monthly cohort remain active over time.

        **How to read the table:**
        - **Rows**: Each cohort (customers who started in a specific month)
        - **Columns**: Months since cohort start (M0, M1, M2, ...)
        - **Values**: Percentage of original cohort still active
        - **Colors**: Green = high retention, Yellow = medium, Red = low retention

        **Why cohort analysis matters:**
        - Which cohorts retain better? (seasonal patterns?)
        - When do customers typically churn? (onboarding issue?)
        - Long-term retention trends

        **Note:**
        - Retention is based on presence in data, not amount
        - Customers with amount = 0 are still counted as retained
        - Paused/discounted subscriptions count as retained
        - Requires at least 3 cohorts to display
        """)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4: FAQ
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    st.header("❓ Frequently Asked Questions")

    with st.expander("🔒 Is my data secure?"):
        st.markdown("""
        **Yes.** SubAudit does not store your CSV data on our servers.

        - All processing happens **in-memory** during your session
        - Data is cleared when you close the browser or session expires
        - We use **Supabase** for authentication (magic link, no passwords)
        - We use **Sentry** for error monitoring with PII filtering
        - Aggregated metrics (NOT raw data) are saved in Supabase only for **signed-in users**
        - Your subscription data **never leaves your session**
        """)

    with st.expander("📊 How much historical data do I need?"):
        st.markdown("""
        **Minimum: 2 months** (for basic metrics like Churn Rate and NRR)

        **Recommended: 6+ months** for:
        - Accurate revenue forecasts (3 scenarios)
        - Cohort retention analysis
        - Seasonal trend detection

        **Forecast availability:**
        - < 3 months: No forecast
        - 3–5 months: Realistic scenario only (with warning)
        - 6+ months: All 3 scenarios (Pessimistic, Realistic, Optimistic)

        **Cohort analysis:**
        - < 3 months: No cohort table
        - 3+ months: Cohort retention heatmap available
        """)

    with st.expander("💰 What if I have multiple currencies?"):
        st.markdown("""
        **SubAudit currently supports single-currency analysis only.**

        If your CSV contains multiple currencies, the upload will be rejected with an error message.

        **Workaround:**
        1. Filter your data to a single currency before upload
        2. Convert all amounts to a base currency (e.g., USD) using historical exchange rates
        3. Upload separate files for each currency and analyze separately

        Multi-currency support is on our roadmap.
        """)

    with st.expander("📈 Why is my NRR > 200%?"):
        st.markdown("""
        **This usually happens when:**
        - You have limited previous month data
        - Many customers are new or reactivated
        - Your dataset starts mid-year (missing earlier cohorts)

        **What to do:**
        - Upload more historical data (6+ months recommended)
        - Check if your previous month data is complete
        - NRR stabilizes as you add more months

        This is a known limitation with small datasets.
        """)

    with st.expander("🔄 What counts as a reactivation?"):
        st.markdown("""
        **Reactivation = customer returns after 2–9 months absence**

        **Rules:**
        - Customer must have been active before
        - Must have been absent for 2–9 months
        - Returns with status = 'active'

        **Exclusions:**
        - 1 month absence = NOT reactivation (just a gap)
        - 10+ months absence = NOT reactivation (too long, treated as new)
        - Annual subscriptions (amount > 6× ARPU) = NOT reactivation
        """)

    with st.expander("📉 Why is my forecast not showing?"):
        st.markdown("""
        **Possible reasons:**

        1. **Not enough data**: You need at least 3 months of historical data
        2. **Sparse data**: Too many gaps in your monthly data
        3. **Forecast failed**: Holt-Winters algorithm couldn't fit your data (too volatile)

        **What you'll see:**
        - < 3 months: "Upgrade to Starter or PRO to access forecast"
        - 3–5 months: Only Realistic scenario (with warning)
        - 6+ months: All 3 scenarios
        - Sparse/failed: Info message explaining why

        **Note:** Forecast is available on **Starter ($9/mo)** and **Pro ($19/mo)** plans only.
        """)

    with st.expander("💳 What is the Growth Simulation?"):
        st.markdown("""
        **What it is:**
        A what-if scenario planner that models the impact of growth levers on your MRR over 12 months.

        **What you can model:**
        - **Churn reduction**: What if we reduce churn by X%?
        - **New customers**: What if we add X new customers per month?
        - **Price increase**: What if we raise prices by X%?

        **Who can use it:**
        Growth Simulation is available on the **Pro plan ($19/mo)** only.

        **⚠️ Known Limitation:**
        Results assume uniform ARPU across all subscribers. With mixed pricing tiers,
        actual revenue impact may differ by 30–60%. Mixed-tier modelling is on the v2 roadmap.
        """)

    with st.expander("🔐 How does sign-in work? Is a password required?"):
        st.markdown("""
        **No password needed — we use Magic Links.**

        1. Enter your email on the Account page
        2. We send you a one-time login link to your inbox
        3. Click the link to sign in
        4. No password to remember or forget

        **Benefits:**
        - No password security risks
        - Works with any email provider
        - Easy to share access within your team

        **Note:** You can use SubAudit without signing in (Free plan), but your data will not be saved between sessions.
        """)

    with st.expander("📄 How does the PDF / Excel export work?"):
        st.markdown("""
        **PDF Export:**
        - **Free**: PDF with "SubAudit" watermark
        - **Starter**: PDF without watermark
        - **Pro**: Branded PDF with your company name

        **Excel Export:**
        - **Free**: Not available
        - **Starter / Pro**: Excel file with formulas (not hardcoded values)

        **Note:** Both exports are re-verified against Gumroad before generation —
        if your plan was downgraded, you'll see a warning before exporting.
        """)

    with st.expander("🐛 I found a bug — what do I do?"):
        st.markdown("""
        **We'd love to hear from you!**

        - **Email**: [biz.sardorbek@gmail.com](mailto:biz.sardorbek@gmail.com)
        - Please include:
          - Description of the issue
          - Steps to reproduce
          - Expected vs actual behavior
          - Screenshots (if applicable)

        **⚠️ Important:** Do NOT share your actual CSV data. Use our
        [sample file](#) or anonymized data.
        """)

    with st.expander("📚 Where can I learn more about SaaS metrics?"):
        st.markdown("""
        **Recommended resources:**

        - [SaaS Metrics 2.0](https://www.forentrepreneurs.com/saas-metrics-2/) by David Skok
        - [The SaaS CFO](https://www.thesaascfo.com/) by Ben Murray
        - [Bessemer Cloud Index](https://www.bvp.com/atlas/cloud-index) — public SaaS benchmarks
        - [OpenView SaaS Benchmarks](https://openviewpartners.com/benchmarks/)

        **Key concepts:**
        - Unit economics (LTV / CAC ratio)
        - Rule of 40 (Growth Rate + Profit Margin > 40%)
        - Magic Number (ARR growth / Sales & Marketing spend)
        """)

    st.divider()

    st.markdown("""
    <div style='text-align: center; color: #666; padding: 20px;'>
        <p>Still have questions? Email us at <strong>biz.sardorbek@gmail.com</strong></p>
        <p style='font-size: 0.9em;'>SubAudit v3.3 | Built for subscription businesses</p>
    </div>
    """, unsafe_allow_html=True)
