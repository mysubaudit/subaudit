import streamlit as st
import pandas as pd
from io import StringIO

st.set_page_config(page_title="Help & Guide", page_icon="❓", layout="wide")

st.title("❓ Help & User Guide")

# Quick navigation
st.markdown("""
<style>
.nav-link {
    padding: 8px 16px;
    margin: 4px;
    background: #f0f2f6;
    border-radius: 4px;
    display: inline-block;
}
</style>
""", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("📊 Quick Start"):
        st.session_state.help_section = "quick_start"
with col2:
    if st.button("📁 CSV Format"):
        st.session_state.help_section = "csv_format"
with col3:
    if st.button("📈 Metrics Guide"):
        st.session_state.help_section = "metrics"
with col4:
    if st.button("❓ FAQ"):
        st.session_state.help_section = "faq"

if "help_section" not in st.session_state:
    st.session_state.help_section = "quick_start"

st.divider()

# Quick Start Section
if st.session_state.help_section == "quick_start":
    st.header("🚀 Quick Start Guide")

    st.markdown("""
    ### Get insights from your subscription data in 3 simple steps:

    **Step 1: Upload Your Data** 📤
    - Go to the **Upload** page
    - Upload your CSV file with subscription data
    - Supported formats: CSV files with customer transactions
    - Maximum file size: 200 MB
    - Processing time: ~5-30 seconds depending on file size

    **Step 2: Map Your Columns** 🗺️
    - SubAudit will automatically detect your column names
    - Confirm or adjust the mapping:
      - **Customer ID**: unique identifier for each customer
      - **Date**: billing/transaction date
      - **Amount**: subscription amount (MRR)
      - **Status**: subscription status (active, churned, trial, etc.)
      - **Currency**: optional, but recommended

    **Step 3: View Your Dashboard** 📊
    - Navigate to **Dashboard** to see:
      - Key metrics (MRR, ARR, ARPU, Churn Rate, NRR, LTV)
      - Revenue forecast (12 months ahead)
      - Cohort retention analysis
      - Growth simulation scenarios
    - Export reports as PDF or Excel
    """)

    st.info("💡 **Tip**: Start with at least 3 months of historical data for accurate metrics and forecasts.")

    st.divider()

    st.subheader("📥 Download Sample CSV")
    st.markdown("Not sure about the format? Download our sample file to see the expected structure.")

    # Generate sample CSV
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

# CSV Format Section
elif st.session_state.help_section == "csv_format":
    st.header("📁 CSV File Requirements")

    st.markdown("""
    ### Required Columns

    Your CSV file must contain these 4 columns (names can vary, we'll detect them):

    | Column | Description | Example Values |
    |--------|-------------|----------------|
    | **Customer ID** | Unique identifier for each customer | `C001`, `user_123`, `cust-456` |
    | **Date** | Billing or transaction date | `2024-01-01`, `01/15/2024` |
    | **Amount** | Subscription amount (MRR) | `99.99`, `1000.00` |
    | **Status** | Subscription status | `active`, `churned`, `trial`, `paused` |

    ### Optional Column

    | Column | Description | Example Values |
    |--------|-------------|----------------|
    | **Currency** | Currency code (recommended for multi-currency) | `USD`, `EUR`, `GBP` |

    ⚠️ **Important**: If you have multiple currencies in your data, SubAudit will reject the file.
    Please filter to a single currency before uploading.
    """)

    st.divider()

    st.subheader("✅ Data Quality Tips")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        **DO:**
        - ✅ Include at least 3 months of data
        - ✅ Use consistent date format
        - ✅ Include all customer transactions
        - ✅ Use lowercase status values
        - ✅ Remove duplicates before upload
        """)

    with col2:
        st.markdown("""
        **DON'T:**
        - ❌ Mix multiple currencies
        - ❌ Include empty rows
        - ❌ Use special characters in Customer ID
        - ❌ Upload files larger than 200 MB
        - ❌ Include aggregated data (use raw transactions)
        """)

    st.divider()

    st.subheader("🔍 What Happens During Upload?")

    st.markdown("""
    1. **Encoding Detection**: We automatically detect your file's character encoding
    2. **Duplicate Removal**: Duplicate rows are identified and removed
    3. **Status Normalization**: Status values are converted to lowercase
    4. **Data Quality Check**: We flag:
       - Rows with amount = 0
       - Rows with negative amounts (refunds/credits)
       - Missing previous month data (affects some metrics)

    You'll see a detailed cleaning report on the **Cleaning** page.
    """)

# Metrics Guide Section
elif st.session_state.help_section == "metrics":
    st.header("📈 Metrics Explained")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "MRR", "ARR", "ARPU", "Churn Rate", "NRR", "LTV", "Cohort Analysis"
    ])

    with tab1:
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

    with tab2:
        st.subheader("📊 ARR (Annual Recurring Revenue)")
        st.markdown("""
        **What it is:**
        Your MRR projected over 12 months.

        **Formula:**
        `ARR = MRR × 12`

        **Why it matters:**
        ARR is the standard metric for B2B SaaS valuation and investor discussions.

        **Typical benchmarks:**
        - $1M ARR = seed stage milestone
        - $10M ARR = Series A milestone
        - $100M ARR = late-stage growth
        """)

    with tab3:
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
        - Reduce discounts

        **Note:**
        - Rows with amount = 0 are excluded from ARPU calculation
        """)

    with tab4:
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
        - **Good**: 3-5% monthly (30-50% annual)
        - **Needs improvement**: 5-7% monthly (50-60% annual)
        - **Critical**: > 7% monthly (> 60% annual)

        **Note:**
        - Requires at least 2 months of data
        - If previous month data is missing, churn rate will show "N/A"
        """)

    with tab5:
        st.subheader("🔄 NRR (Net Revenue Retention)")
        st.markdown("""
        **What it is:**
        Percentage of revenue retained from existing customers, including expansions and contractions.

        **Formula:**
        ```
        NRR = ((MRR_current - New_MRR + Reactivation_MRR) / MRR_previous) × 100%
        ```

        **Why it matters:**
        NRR > 100% means you're growing revenue from existing customers even without new signups.

        **Benchmarks:**
        - **World-class**: > 120% (best-in-class SaaS)
        - **Excellent**: 110-120%
        - **Good**: 100-110%
        - **Needs improvement**: 90-100%
        - **Critical**: < 90%

        **⚠️ Warning:**
        If NRR > 200%, it usually indicates limited previous month data. This is common in early-stage datasets.

        **Note:**
        - Requires at least 2 months of data
        - Reactivation = customers who return after 2-9 months absence
        - Annual subscriptions (amount > 6× ARPU) are excluded from reactivation
        """)

    with tab6:
        st.subheader("💎 LTV (Lifetime Value)")
        st.markdown("""
        **What it is:**
        Expected total revenue from a customer over their entire subscription lifetime.

        **Formula:**
        ```
        LTV = ARPU / Churn Rate
        ```

        **Special case:**
        If Churn Rate = 0%, we cap LTV at `ARPU × 36 months` to avoid infinity.

        **Why it matters:**
        LTV helps you determine how much you can spend on customer acquisition (CAC).
        Rule of thumb: `LTV / CAC > 3` is healthy.

        **Example:**
        - ARPU = $100
        - Churn Rate = 5%
        - LTV = $100 / 0.05 = $2,000

        **⚠️ Known Limitation:**
        LTV is capped at 36 months. Do NOT use this for unit economics or CAC payback calculations
        if your actual customer lifetime exceeds 3 years.
        """)

    with tab7:
        st.subheader("📅 Cohort Retention Analysis")
        st.markdown("""
        **What it is:**
        Tracks how many customers from each monthly cohort remain active over time.

        **How to read the table:**
        - **Rows**: Each cohort (customers who started in a specific month)
        - **Columns**: Months since cohort start (M0, M1, M2, ...)
        - **Values**: Percentage of original cohort still active

        **Example:**
        ```
        Cohort: Jan 2024
        M0: 100% (all customers start active)
        M1: 85% (15% churned in first month)
        M2: 75% (10% more churned in second month)
        M3: 70% (5% more churned in third month)
        ```

        **Why it matters:**
        Cohort analysis reveals:
        - Which cohorts have better retention (seasonal patterns?)
        - When customers typically churn (onboarding issue?)
        - Long-term retention trends

        **Note:**
        - Retention is based on presence in data, not amount
        - Customers with amount = 0 are still counted as retained
        - Paused/discounted subscriptions count as retained
        - Requires at least 3 cohorts to display
        """)

# FAQ Section
elif st.session_state.help_section == "faq":
    st.header("❓ Frequently Asked Questions")

    with st.expander("🔒 Is my data secure?"):
        st.markdown("""
        **Yes.** SubAudit does not store your CSV data on our servers.

        - All processing happens in-memory during your session
        - Data is cleared when you close the browser or session expires
        - We use Supabase for authentication (magic link, no passwords)
        - We use Sentry for error monitoring with PII filtering

        Your subscription data never leaves your session.
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
        - 3-5 months: Realistic scenario only (with warning)
        - 6+ months: All 3 scenarios (Pessimistic, Realistic, Optimistic)
        """)

    with st.expander("💰 What if I have multiple currencies?"):
        st.markdown("""
        **SubAudit currently supports single-currency analysis only.**

        If your CSV contains multiple currencies, the upload will be rejected with an error message.

        **Workaround:**
        1. Filter your data to a single currency before upload
        2. Convert all amounts to a base currency (e.g., USD) using historical exchange rates
        3. Upload separate files for each currency and analyze separately

        Multi-currency support is on our roadmap for v2.
        """)

    with st.expander("📈 Why is my NRR > 200%?"):
        st.markdown("""
        **This usually happens when:**
        - You have limited previous month data
        - Many customers are new or reactivated
        - Your dataset starts mid-year (missing earlier cohorts)

        **Example:**
        - Previous month MRR: $1,000 (only 5 customers)
        - Current month MRR: $5,000 (50 customers)
        - NRR = ($5,000 - $4,000 new) / $1,000 = 100%... but if reactivations are high, NRR can spike

        **What to do:**
        - Upload more historical data (6+ months recommended)
        - Check if your previous month data is complete
        - NRR stabilizes as you add more months

        This is a known limitation with small datasets.
        """)

    with st.expander("🔄 What counts as a reactivation?"):
        st.markdown("""
        **Reactivation = customer returns after 2-9 months absence**

        **Rules:**
        - Customer must have been active before
        - Must have been absent for 2-9 months
        - Returns with status = 'active'

        **Exclusions:**
        - 1 month absence = NOT reactivation (just a gap)
        - 10+ months absence = NOT reactivation (too long, treated as new)
        - Annual subscriptions (amount > 6× ARPU) = NOT reactivation

        **Why exclude annual subscriptions?**
        Annual customers pay once per year, so a 2-9 month gap is normal, not a reactivation.
        """)

    with st.expander("📉 Why is my forecast not showing?"):
        st.markdown("""
        **Possible reasons:**

        1. **Not enough data**: You need at least 3 months of historical data
        2. **Sparse data**: Too many gaps in your monthly data
        3. **Forecast failed**: HoltWinters algorithm couldn't fit your data (too volatile)

        **What you'll see:**
        - < 3 months: "Not enough data for forecast"
        - 3-5 months: Only Realistic scenario (with warning)
        - 6+ months: All 3 scenarios
        - Sparse/failed: Info message explaining why

        **How to fix:**
        - Upload more months of data
        - Ensure you have data for consecutive months (no large gaps)
        """)

    with st.expander("💳 What's the difference between Free, Starter, and Pro?"):
        st.markdown("""
        | Feature | Free | Starter | Pro |
        |---------|------|---------|-----|
        | **Upload & Analysis** | ✅ | ✅ | ✅ |
        | **Dashboard Metrics** | ✅ | ✅ | ✅ |
        | **Cohort Analysis** | ✅ | ✅ | ✅ |
        | **Revenue Forecast** | ✅ | ✅ | ✅ |
        | **PDF Export** | ⚠️ Watermarked | ✅ No watermark | ✅ No watermark |
        | **Excel Export** | ❌ | ✅ | ✅ |
        | **Growth Simulation** | ❌ | ❌ | ✅ |

        **Free Plan:**
        - Full dashboard access
        - PDF export with "SubAudit Free Plan" watermark
        - No Excel export
        - No simulation

        **Starter Plan ($29/month):**
        - Everything in Free
        - PDF without watermark
        - Excel export with formulas

        **Pro Plan ($99/month):**
        - Everything in Starter
        - Growth simulation (what-if scenarios)
        - Priority support

        Visit the **Pricing** page to upgrade.
        """)

    with st.expander("🐛 I found a bug or have a feature request"):
        st.markdown("""
        **We'd love to hear from you!**

        - **GitHub Issues**: [github.com/mysubaudit/subaudit/issues](https://github.com/mysubaudit/subaudit/issues)
        - **Email**: support@subaudit.com

        Please include:
        - Description of the issue
        - Steps to reproduce
        - Expected vs actual behavior
        - Screenshots (if applicable)

        **Note**: Do NOT share your actual CSV data. Use our sample file or anonymized data.
        """)

    with st.expander("📚 Where can I learn more about SaaS metrics?"):
        st.markdown("""
        **Recommended resources:**

        - [SaaS Metrics 2.0](https://www.forentrepreneurs.com/saas-metrics-2/) by David Skok
        - [The SaaS CFO](https://www.thesaascfo.com/) by Ben Murray
        - [Bessemer Cloud Index](https://www.bvp.com/atlas/cloud-index) - public SaaS benchmarks
        - [OpenView SaaS Benchmarks](https://openviewpartners.com/benchmarks/)

        **Key concepts:**
        - Unit economics (LTV / CAC ratio)
        - Rule of 40 (Growth Rate + Profit Margin > 40%)
        - Magic Number (ARR growth / Sales & Marketing spend)
        - Payback period (months to recover CAC)
        """)

st.divider()

st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>Still have questions? Email us at <strong>support@subaudit.com</strong></p>
    <p style='font-size: 0.9em;'>SubAudit v1.0 | Built with ❤️ for subscription businesses</p>
</div>
""", unsafe_allow_html=True)
