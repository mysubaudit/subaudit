# SubAudit

**SaaS metrics for non-Stripe founders. Any billing source, any CSV — $9/month instead of $129.**

Upload a subscription CSV → get MRR, ARR, churn, NRR, LTV, cohort analysis and a 12-month forecast in under 60 seconds.

🔗 **Live app:** [subaudit.streamlit.app](https://subaudit.streamlit.app)

---

## Why SubAudit

ChartMogul and Baremetrics charge $99-130/month and only work well with Stripe. Founders who use **Paddle, Gumroad, LemonSqueezy, Chargebee, or manual invoicing** are stuck with spreadsheets.

SubAudit takes any CSV — from any source — and produces the same SaaS metrics for $9/month.

---

## Features

- **5 metric blocks:** Revenue, Growth, Retention, Health, Cohort analysis
- **Forecast:** 12-month projection (Holt-Winters), 3 scenarios with ≥6 months of data
- **PDF + Excel export** with working formulas
- **Privacy:** all CSVs processed in-memory, never written to disk
- **No password:** magic-link auth via Supabase
- **Multi-source CSV** (Stripe / Paddle / Gumroad / LemonSqueezy / Chargebee / manual)

---

## Pricing

| Plan | Price | Rows | Metrics | Excel | Forecast |
|------|-------|------|---------|-------|----------|
| FREE | $0 | 1,000 | Blocks 1-2 | — | — |
| STARTER | $9/mo | 10,000 | All 5 | ✓ | ✓ |
| PRO | $19/mo | 50,000 | All 5 | ✓ + Simulation | ✓ |

---

## Tech stack

Python 3.11.9 · Streamlit 1.35 · Supabase · Gumroad · Sentry · ReportLab · openpyxl

---

## Run locally

```bash
pip install -r requirements.txt
streamlit run app/main.py
```

Set up `.streamlit/secrets.toml` with `SUPABASE_URL`, `SUPABASE_KEY`,
`GUMROAD_ACCESS_TOKEN`, `SENTRY_DSN`. See [SPEC.md §4](./SPEC.md) for the full stack.

---

## Documentation

- **[SPEC.md](./SPEC.md)** — technical specification (v3.0)
- **[STRATEGY.md](./STRATEGY.md)** — business strategy, target audience, roadmap
- **[CLAUDE.md](./CLAUDE.md)** — AI assistant instructions
- **[docs/FAQ.md](./docs/FAQ.md)** — user FAQ
- **[docs/DATA_PREPARATION.md](./docs/DATA_PREPARATION.md)** — CSV preparation guide

---

## Contact

biz.sardorbek@gmail.com