# SubAudit — Specification v3.0

**Version:** 3.0
**Last updated:** 2026-05-22 (тесты зафиксированы, проект готов к v3.1)
**Supersedes:** SubAudit_Spec.docx (v2.x, removed)

**Current status:**
- ✅ v3.0 документация завершена (SPEC.md, STRATEGY.md, CLAUDE.md переписаны)
- ✅ LemonSqueezy → Gumroad миграция завершена
- ✅ **308/308 тестов проходят**
- ✅ v3.1 Voluntary vs Involuntary Churn split — реализовано
- ✅ v3.2.1 Каталог сигнатур — реализовано
- ✅ v3.2.2 Детектор формата — реализовано (+25 тестов)
- ⏳ v3.2.3 Интеграция в upload flow — следующий шаг

---

## 1. What is SubAudit

SubAudit is a web app that turns a subscription CSV into SaaS metrics
(MRR, ARR, churn, NRR, LTV, cohort analysis, forecast) in under 60 seconds.

**One-line positioning:**
> SaaS metrics for non-Stripe founders. Any billing source, any CSV — $9/month instead of $129.

**Why this positioning (validated from real user complaints, May 2026):**
- ChartMogul / Baremetrics charge $99-130/mo and only support Stripe well
- Founders using Paddle, Gumroad, LemonSqueezy, Chargebee, or manual invoicing
  cannot use them effectively (real quote, r/SaaS:
  *"I can't use stripe metrics since I have a lot of manual invoices"*)
- These founders fall back to Google Sheets and lose 2 hours every month

SubAudit fills this gap.

---

## 2. Target audience (validated)

### Primary: Non-Stripe micro-SaaS founders ($1K-50K MRR)
- Use Paddle / Gumroad / LemonSqueezy / Chargebee / manual invoicing
- Cannot justify $100+/mo for analytics
- Currently track metrics in spreadsheets

### Secondary: Bootstrapped Stripe founders (<$10K MRR)
- Stripe analytics are limited (no cohorts, no LTV, hides involuntary churn)
- $99/mo ChartMogul is too expensive at this stage
- Want a $9 alternative for the basics

### Not the audience (explicitly):
- VC-funded $1M+ ARR companies (they buy ChartMogul)
- Pre-revenue founders (no metrics to analyze)
- Technical founders who write SQL (they DIY)

---

## 3. Core value proposition

| What founder wants | How SubAudit delivers |
|--------------------|----------------------|
| Cheap metrics | $9/mo vs $99+/mo competitors |
| Works with my billing | CSV upload, any source |
| See real churn (not hidden) | Voluntary vs involuntary churn split (v3.1) |
| Track changes over time | Snapshot history (v3.3) |
| Professional report | PDF export, no watermark on paid plans |

---

## 4. Tech stack (frozen until $500 MRR)

| Component | Choice | Why this, not other |
|-----------|--------|---------------------|
| Language | Python 3.11.9 | Streamlit requirement |
| Framework | Streamlit 1.35.0 | Free hosting, fast to build |
| Hosting | Streamlit Community Cloud | Free, sufficient until 50+ DAU |
| Auth | Supabase (magic link) | Free tier, no password complexity |
| Payments | Gumroad | No company registration required |
| Errors | Sentry free tier | Free 5K events/month |
| PDF | ReportLab 4.1.0 | Pure Python, in-memory only |
| Excel | openpyxl 3.1.2 | Pure Python, formula support |
| Fuzzy match | rapidfuzz 3.9.3 | NOT fuzzywuzzy (deprecated) |
| Encoding | charset-normalizer | NOT chardet (license issue) |

**Migration triggers:** Move to a paid stack only when MRR > $500 AND current
stack hits a hard limit (RAM, concurrency, Gumroad fees).

---

## 5. File structure

```
app/
├── main.py
├── pages/
│   ├── 1_landing.py
│   ├── 2_upload.py
│   ├── 3_mapping.py
│   ├── 4_cleaning.py
│   ├── 5_dashboard.py
│   ├── 6_pricing.py
│   ├── 7_account.py
│   └── auth_callback.py
├── core/
│   ├── mapper.py
│   ├── cleaner.py
│   ├── metrics.py
│   ├── forecast.py
│   └── simulation.py
├── reports/
│   ├── pdf_builder.py
│   └── excel_builder.py
├── auth/
│   └── supabase_auth.py
├── payments/
│   └── gumroad.py
└── observability/
    └── logger.py
docs/
tests/
```

---

## 6. Pricing (current, frozen until validation)

| Plan | Price | Login | Max rows | Metrics | Excel | Forecast | Simulation | PDF |
|------|-------|-------|----------|---------|-------|----------|------------|-----|
| FREE | $0 | No | 1,000 | Blocks 1-2 | No | No | No | Watermark |
| STARTER | $9/mo | Yes | 10,000 | All 5 | Yes | Yes (≥3 mo) | No | No watermark |
| PRO | $19/mo | Yes | 50,000 | All 5 | Yes | Yes | Yes | Branded |

**Pricing change rule:** Do not raise prices until at least 10 paying users
provide feedback. "Charge more" advice without paying users is premature.

---

## 7. Metrics (5 blocks)

### Block 1 — Revenue
- MRR (Monthly Recurring Revenue)
- ARR (Annual Recurring Revenue)
- ARPU (Average Revenue Per User)
- Total Revenue

### Block 2 — Growth
- New MRR
- Reactivation MRR
- Growth Rate
- New Subscribers

### Block 3 — Retention (Starter+)
- Churn Rate (logo)
- Revenue Churn (gross / net / voluntary / involuntary — see §8)
- NRR (Net Revenue Retention, clamped 0-999%)

### Block 4 — Health (Starter+)
- LTV (capped at 36 × ARPU when churn = 0)
- Active / Lost / Existing Subscribers

### Block 5 — Cohort Analysis (Starter+)
- Up to 12 monthly cohorts
- Retention heatmap
- Asymmetric definition: entry by amount > 0, retention by status (intentional)

### Forecast (Starter+, ≥3 months data)
- Holt-Winters exponential smoothing
- 3 months → Realistic only
- 6+ months → Pessimistic / Realistic / Optimistic

### Simulation (Pro only)
- What-if scenarios (churn ↓, price ↑)
- KNOWN LIMITATION: assumes uniform ARPU, error 30-60% on mixed-tier pricing

---

## 8. Roadmap (priority by validated pain)

### v3.1 — Voluntary vs Involuntary Churn split
**Validated pain:** r/SaaS — *"Stripe doesn't separate failed payments from
intentional cancellations. A customer who hated your product and a customer
whose card expired look the same."* 40-60% of "churn" is recoverable.

**Implementation:** Read status column, split into:
- Voluntary churn (status = cancelled)
- Involuntary churn (status = past_due / payment_failed)
- Show separately on dashboard, in PDF, in Excel

**Effort:** 1 day. UI + one formula. **Unique to SubAudit.**

### v3.2 — Multi-source CSV presets (6 подшагов)
**Validated pain:** r/SaaS — *"I can't use Stripe metrics since I have a lot
of manual invoices"*. ChartMogul/Baremetrics are Stripe-only.

**Implementation:** Auto-detect CSV format by column signature.
Presets: Stripe, Paddle, Gumroad, LemonSqueezy, Chargebee, manual.
Skip mapping page when format is recognized.

**Effort:** 2-3 дня (каждый подшаг ~30-60 мин).

| # | Подшаг | Что делает | DoD |
|---|--------|-----------|-----|
| v3.2.1 | Каталог сигнатур | Словарь `_PRESET_SIGNATURES` в `app/core/presets.py`: 6 источников, каждый с customer_id/date/amount/status | Таблица в комментарии, тесты не требуются |
| v3.2.2 | Детектор формата | `detect_preset(df, columns)` — сравнивает колонки CSV с сигнатурами, возвращает имя пресета или None | 3-4 теста, не ломает mapping |
| v3.2.3 | Интеграция в upload flow | После парсинга CSV вызвать detect_preset(), сохранить в `session_state.preset` | Upload не сломан, детектор молча работает в фоне |
| v3.2.4 | UI на mapping-странице | Зелёный badge с именем пресета, кнопка «это не мой формат» для сброса на manual | UI логика замкнута, нет регрессии в mapping |
| v3.2.5 | Авто-скип mapping | Если пресет распознан — сразу применить mapping без ручного подтверждения (флажок в настройках, default ON) | С sample CSV от Stripe — mapping пропускается |
| v3.2.6 | Документация + финальные тесты | Обновить FAQ, help, SPEC.md, CLAUDE.md; полный прогон тестов | Definition of Done по SPEC.md §9 закрыт |

### v3.3 — Snapshot history (6 подшагов)
**Validated pain:** r/hubspot — *"HubSpot tells current MRR but not what it
was on April 1st 2024. Huge blocker."* + general MoM tracking need.

**Implementation:** Store metrics aggregates (NOT raw CSV) in Supabase per
authenticated user. Show MoM delta on dashboard. Account page shows history.

**Effort:** 2-3 дня (каждый подшаг ~30-60 мин).

| # | Подшаг | Что делает |
|---|--------|-----------|
| v3.3.1 | Supabase таблица `snapshots` | Структура, миграция |
| v3.3.2 | Сохранение метрик | Сохранять после загрузки CSV |
| v3.3.3 | Загрузка истории | MoM дельта для дашборда |
| v3.3.4 | UI: график MRR/churn | График по месяцам |
| v3.3.5 | Account page | Список снапшотов |
| v3.3.6 | Тесты + документация | Полный прогон, обновление docs |

### v4 (later, only if validated by paying users)
- Stripe / Paddle / Gumroad direct integrations (OAuth)
- Scheduled email reports
- Public share links (read-only dashboards)
- Mixed-tier ARPU modeling for Simulation

---

## 9. Hard rules

1. **No data persistence of user CSVs.** Files processed in-memory only
   (`io.BytesIO`). No disk write. No third-party transfer.
2. **DataFrame immutability** — no mutations except in `cleaner.py`.
   Enforced by AST check in `test_immutability.py`.
3. **Secrets never in git.** `.env` and `.streamlit/secrets.toml` are gitignored.
4. **No new feature without validated pain.** Each roadmap item must reference
   a real user complaint (Reddit / IH thread / direct feedback).
5. **English UI, Russian code comments.** UI is for users (English-speaking
   B2B). Code comments are for the developer (Russian).

---

## 10. Known limitations (be honest)

1. **Cohort retention asymmetry** — entry by `amount > 0`, retention by
   `status`. Paused subs count as retained. Intentional.
2. **LTV cap = 36 months × ARPU** when churn = 0. Do not use for unit economics.
3. **NRR clamped to 0-999%.** Values above 200% trigger warning.
4. **Simulation uniform ARPU** — error 30-60% with mixed pricing tiers.
5. **Forecast gate:** <3 months → hidden, 3-5 months → Realistic only,
   ≥6 months → all scenarios.
6. **Streamlit RAM limit ~1 GB** = ~3-4 concurrent PRO sessions max.
   Migration trigger when load testing fails.
7. **Gumroad polling, not webhooks.** 5-minute cache, slight delay possible.

---

## 11. Success metrics (next 90 days)

| Metric | Target | Reality (2026-05-18) |
|--------|--------|----------------------|
| Reddit / IH outbound posts | 10 | 0 |
| FREE signups | 50 | 0 |
| STARTER conversions | 3 | 0 |
| First paying user | 1 | 0 |

**Above $200 MRR:** consider domain, company registration, scheduled reports.
**Below $200 MRR after 90 days:** reposition or shut down.

---

*This file supersedes `SubAudit_Spec.docx`. The .docx was removed in v3.0
because markdown lives in git, diffs cleanly, and is readable by AI assistants
without conversion.*

