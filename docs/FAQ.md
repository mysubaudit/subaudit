# SubAudit — Frequently Asked Questions

**Last updated:** May 18, 2026

---

## General Questions

### What is SubAudit?

SubAudit is a web-based SaaS analytics tool that turns your subscription data into actionable insights. Upload a CSV file with your customer transactions, and get comprehensive metrics including MRR, churn rate, NRR, LTV, cohort analysis, and forecasts — all in under 60 seconds.

### Who is SubAudit for?

SubAudit is designed for:
- SaaS founders tracking their subscription business
- Finance teams analyzing recurring revenue
- Product managers monitoring customer retention
- Analysts preparing board reports

### Do I need to install anything?

No. SubAudit runs entirely in your browser. No downloads, no setup, no integrations required.

---

## Data & Privacy

### What data do I need to upload?

You need a CSV file with your subscription transactions. At minimum, your file should contain:
- **Customer ID** — unique identifier for each customer
- **Transaction Date** — when the subscription was active
- **Amount** — subscription price (in any currency)
- **Status** — subscription state (active, cancelled, paused, etc.)

See our [Data Preparation Guide](DATA_PREPARATION.md) for detailed requirements.

### Is my data safe?

**Yes. Your data never leaves your browser session.**

SubAudit processes all files **in-memory only**. No file is written to disk, stored in a database, or sent to any third party. When you close your browser, all data is permanently deleted.

We do not have access to your subscription data. Period.

### What happens to my data after I close the browser?

It's gone. Permanently. SubAudit does not persist any uploaded files or computed metrics. Each session is isolated and ephemeral.

### Do you store my email address?

Yes, but only for authentication. When you sign up for a paid plan, your email is stored in our authentication system (Supabase) to verify your subscription status. We never share your email with third parties.

### Can I use SubAudit with sensitive customer data?

Yes. Since all processing happens in-memory in your browser, you can safely analyze data containing customer information. However, we recommend:
- Anonymizing customer names before upload (use IDs only)
- Not including payment card numbers or other PII in your CSV
- Reviewing your company's data handling policies before uploading

---

## Plans & Pricing

### What's included in the Free plan?

The Free plan includes:
- Up to 1,000 rows per file
- Revenue & Growth metrics (Blocks 1-2)
- PDF export with watermark
- No credit card required
- No account needed

### What's the difference between Starter and Pro?

| Feature | Free | Starter ($9/mo) | Pro ($19/mo) |
|---------|------|-----------------|--------------|
| Max rows | 1,000 | 10,000 | 50,000 |
| All 5 metric blocks | ✗ | ✓ | ✓ |
| Excel export | ✗ | ✓ | ✓ |
| Forecast | ✗ | ✓ (≥3 months data) | ✓ |
| Simulation dashboard | ✗ | ✗ | ✓ |
| PDF watermark | Yes | No | No |

### How do I upgrade?

1. Go to the **Pricing** page
2. Click "Get Starter" or "Get Pro"
3. Complete payment via Gumroad
4. Your plan activates immediately

### Can I cancel anytime?

Yes. Subscriptions are monthly and can be cancelled at any time from your Account page. No questions asked.

### Do you offer refunds?

Yes. We offer a **7-day money-back guarantee** on all paid plans. If you're not satisfied, email us at **biz.sardorbek@gmail.com** within 7 days of purchase for a full refund.

---

## Using SubAudit

### What file format do I need?

CSV (Comma-Separated Values). Most billing systems and payment processors can export to CSV:
- Stripe → Exports → Subscriptions
- Chargebee → Reports → Subscription Export
- Recurly → Analytics → Export
- Manual spreadsheet → Save As → CSV

### My CSV has different column names. Will it work?

Yes! SubAudit includes a **smart column mapping** step that uses fuzzy matching to automatically detect your columns. You can also manually map columns if needed.

### What if my data has missing values or errors?

SubAudit includes a **data cleaning** step that:
- Detects and reports missing values
- Identifies invalid dates or amounts
- Flags duplicate transactions
- Shows a detailed quality report before analysis

You can review the report and decide whether to proceed or fix issues in your source data.

### How many months of data do I need?

**Minimum:** 1 month (for basic metrics)
**Recommended:** 6+ months (for accurate forecasts and cohort analysis)

Forecast features require:
- **3 months minimum** — shows Realistic scenario only
- **6+ months** — shows all 3 scenarios (Pessimistic, Realistic, Optimistic)

### Can I upload multiple files?

Currently, SubAudit processes **one file per session**. To analyze a different file, upload it and your previous session data will be replaced.

Snapshot history (compare metrics across uploads over time) is planned for v3.3 — see [SPEC.md](../SPEC.md).

### What currencies are supported?

All currencies. SubAudit treats amounts as numbers and preserves your currency symbol. Metrics are calculated correctly regardless of currency, as long as all amounts in your file use the same currency.

**Important:** Do not mix currencies in a single file (e.g., USD and EUR). Convert all amounts to one currency before uploading.

---

## Metrics & Calculations

### What metrics does SubAudit calculate?

SubAudit computes 15+ SaaS metrics across 5 blocks:

**Block 1 — Revenue**
- MRR (Monthly Recurring Revenue)
- ARR (Annual Recurring Revenue)
- ARPU (Average Revenue Per User)
- Total Revenue

**Block 2 — Growth**
- New MRR
- Reactivation MRR
- Growth Rate
- New Subscribers

**Block 3 — Retention**
- Churn Rate
- Revenue Churn (4 scenarios)
- NRR (Net Revenue Retention)

**Block 4 — Health**
- LTV (Lifetime Value, 36-month cap)
- Active Subscribers
- Lost Subscribers
- Existing Subscribers

**Block 5 — Cohort Analysis**
- Up to 12 monthly cohorts
- Retention heatmap

**Forecast** (Starter/Pro, ≥3 months data)
- 12-month MRR projection
- Pessimistic / Realistic / Optimistic scenarios

**Simulation** (Pro only)
- Churn reduction impact
- Price increase scenarios

### How is churn calculated?

Churn Rate = (Lost Subscribers / Active Subscribers at start of month) × 100%

A customer is considered "churned" if they had an active subscription last month but do not appear in the current month's data.

### What is the difference between Voluntary and Involuntary Churn?

SubAudit v3.1 splits churn into two categories based on your data's **Status** column:

- **Voluntary Churn** (status `cancelled`): Customers who intentionally cancelled their subscription. These are customers who chose to leave — the fix is improving your product or pricing.
- **Involuntary Churn** (status `past_due` / `payment_failed`): Customers lost due to failed payments (card expired, insufficient funds). These are recoverable — use dunning emails or payment retry logic.

> **Example:** If your dashboard shows 5% Voluntary Churn and 3% Involuntary Churn, it means 3% of your customers didn't want to leave — their payment just didn't go through. This is actionable insight Stripe doesn't show you.

To use this feature, include the appropriate status in your CSV (e.g., `past_due`, `payment_failed`, `cancelled`). SubAudit automatically normalizes common variants of these statuses.

### Why is my NRR over 100%?

NRR (Net Revenue Retention) over 100% means your existing customers are spending more than they did last month — a sign of healthy expansion revenue (upgrades, add-ons, etc.).

NRR over 200% usually indicates limited data for the previous month. SubAudit will show a warning in this case.

### What does "LTV capped at 36 months" mean?

LTV (Lifetime Value) is calculated as ARPU ÷ Churn Rate. If your churn rate is very low (or zero), this formula can produce unrealistic values (e.g., $100K+ LTV).

SubAudit caps LTV at **36 months of ARPU** to keep estimates grounded. This is intentional and follows industry best practices for early-stage SaaS.

**Note:** Do not use SubAudit's LTV for unit economics or CAC payback calculations. It's designed for high-level health monitoring only.

### How does the forecast work?

SubAudit uses **Holt-Winters exponential smoothing** to project MRR 12 months forward. This method accounts for trends and seasonality in your historical data.

Three scenarios are generated:
- **Pessimistic** — assumes slower growth or higher churn
- **Realistic** — baseline projection
- **Optimistic** — assumes faster growth or lower churn

Forecasts are statistical estimates, not guarantees. Use them for planning, not commitments.

---

## Troubleshooting

### My file won't upload. What's wrong?

Common issues:
- **File too large** — Free plan supports up to 1,000 rows. Upgrade to Starter (10K) or Pro (50K).
- **Not a CSV** — Make sure your file is saved as `.csv`, not `.xlsx` or `.xls`.
- **Encoding issues** — Try saving your CSV as UTF-8 in Excel or Google Sheets.

### I see "N/A" for some metrics. Why?

"N/A" means SubAudit couldn't calculate that metric due to insufficient data. Common reasons:
- **No previous month data** — Churn, NRR, and Growth Rate require at least 2 months of data.
- **Zero active subscribers** — ARPU and LTV require active customers.
- **Missing amounts** — Revenue metrics require valid numeric amounts.

Check the **Data Quality** section in your dashboard for details.

### The forecast is empty. Why?

Forecast requires **at least 3 months of data**. If you have fewer than 3 months, the forecast section will not appear.

With 3-5 months of data, only the Realistic scenario is shown (with a warning). For all 3 scenarios, you need 6+ months.

### My subscription isn't recognized after upgrading.

If you just upgraded and SubAudit still shows "Free":
1. Refresh the page (Ctrl+R or Cmd+R)
2. Wait 1-2 minutes for Gumroad to sync
3. Check your email for the purchase confirmation
4. If still not working, email us at **biz.sardorbek@gmail.com** with your order number

### I found a bug. How do I report it?

Email us at **biz.sardorbek@gmail.com** with:
- Description of the issue
- Steps to reproduce
- Screenshot (if applicable)
- Your plan tier (Free/Starter/Pro)

We respond within 2 business days.

---

## Technical Questions

### What technology does SubAudit use?

- **Frontend:** Streamlit (Python web framework)
- **Backend:** Python 3.11
- **Hosting:** Streamlit Community Cloud
- **Auth:** Supabase (magic link, no passwords)
- **Payments:** Gumroad
- **Monitoring:** Sentry

### Is SubAudit open source?

No. SubAudit is proprietary software. However, we're transparent about our data handling practices and privacy guarantees.

### Can I integrate SubAudit with my billing system?

Not yet. SubAudit currently requires manual CSV upload. CSV auto-detection for Stripe / Paddle / Gumroad / LemonSqueezy / Chargebee formats is planned for v3.2 — once the file is uploaded, no mapping step will be needed.

Direct OAuth integrations are not on the near-term roadmap. SubAudit's CSV-first approach is intentional: it supports any billing source, including manual invoicing.

### Do you have a mobile app?

No. SubAudit is a web application optimized for desktop browsers. It works on mobile browsers but the experience is best on a laptop or desktop.

---

## Contact & Support

### How do I get help?

Email us at **biz.sardorbek@gmail.com**

We respond within 2 business days (usually faster).

### Do you offer onboarding or training?

For Pro plan customers, we offer a free 30-minute onboarding call to help you:
- Prepare your data correctly
- Understand your metrics
- Set up recurring analysis workflows

Email us to schedule: **biz.sardorbek@gmail.com**

### Can I request a feature?

Yes! We love hearing from users. Email your feature request to **biz.sardorbek@gmail.com** and we'll add it to our roadmap.

---

**Still have questions?** Email us at **biz.sardorbek@gmail.com**
