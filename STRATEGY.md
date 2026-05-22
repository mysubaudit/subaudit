# SubAudit — Strategy

**Last updated:** 2026-05-18
**Supersedes:** PRODUCT_STRATEGY.md (renamed, rewritten with validated data)

> This document records WHY SubAudit exists and WHO will pay.
> Every claim below is backed by a real user complaint with a source link.
> No assumptions, no "I think" — only quotes from people who already feel the pain.

---

## 1. The problem (validated, May 2026)

Bootstrapped SaaS founders below $50K MRR have three options for subscription
analytics, and all three are broken:

### Option A: ChartMogul / Baremetrics ($99-130/mo)
Too expensive. Real quotes:

- *"was paying $129/mo for Baremetrics to see my own data"*
  — [r/SaaS post title](https://www.reddit.com/r/SaaS/comments/1rx3i1l/)
- *"hit the 10k MRR mark last year and I'm paying $120 per month, which is
  just too much for what I'm using it for"*
  — [r/SaaS, ChartMogul Alternative](https://www.reddit.com/r/SaaS/comments/1qdji6a/)
- *"Tools like Baremetrics or ChartMogul cost $100+ per month. As a
  bootstrapped founder, I couldn't justify that cost"*
  — [r/SaaS, RevPilot launch](https://www.reddit.com/r/SaaS/comments/1rsz65q/)
- *"Baremetrics charges $108/month for roughly the same thing on Stripe.
  ChartMogul starts at $99"*
  — [r/SaasDevelopers, Indian founder](https://www.reddit.com/r/SaasDevelopers/comments/1stf02b/)

### Option B: Stripe built-in analytics
Limited and misleading:

- *"Stripe shows transactions, but not the story behind the revenue. Once
  you can see churn timing, cohort decay, and LTV clearly, growth decisions
  become way easier."*
  — [r/SaaS](https://www.reddit.com/r/SaaS/comments/1rsz65q/)
- *"Stripe doesn't separate [failed payments from cancellations]. A customer
  who hated your product and a customer whose card expired look the same."*
  — [r/SaaS, "How to check if Stripe is hiding churn"](https://www.reddit.com/r/SaaS/comments/1r7052c/)
- Stripe also can't help founders who use **Paddle, Gumroad, LemonSqueezy,
  Chargebee, or manual invoicing** — the entire non-Stripe market.

### Option C: Google Sheets (the actual competitor)
Cheap but painful:

- *"founders hack spreadsheets every month because ChartMogul and
  Baremetrics charge a limb"*
  — [r/SaaS](https://www.reddit.com/r/SaaS/comments/1mwcvkr/)
- *"basic version is a weekly export of subscriptions + invoices into a
  spreadsheet, tag each row as new/upgrade/downgrade/cancel, then let
  formulas do the rest"*
  — [r/SaaS](https://www.reddit.com/r/SaaS/comments/1r73wbk/)
- *"I would also advise others to do the same, save some $$$ this way and
  do it manually"*
  — [IndieHackers](https://www.indiehackers.com/post/is-it-just-me-do-you-track-your-saas-metrics-in-google-sheets-30f3ce72a5)

**The opportunity:** SubAudit at $9-19/mo sits in the gap between $0
(Sheets) and $99 (ChartMogul). The gap is real and people complain about
it constantly.

---

## 2. Target audience (validated)

### Primary: Non-Stripe micro-SaaS founders ($1K-50K MRR)
- Use Paddle / Gumroad / LemonSqueezy / Chargebee / manual invoicing
- Why they cannot use ChartMogul: *"I can't use Stripe metrics since I have
  a lot of manual invoices that are not reflected"*
  ([r/SaaS](https://www.reddit.com/r/SaaS/comments/1qdji6a/))
- Why they cannot use Sheets long-term: 2 hours/month of manual work
- **This is the underserved niche. Existing tools ignore them.**

### Secondary: Bootstrapped Stripe founders (<$10K MRR)
- Can technically use ChartMogul but $99/mo eats 1% of MRR
- Want cohorts, LTV, voluntary/involuntary churn split — Stripe hides it
- Will use SubAudit until they hit $20K MRR and "afford" ChartMogul

### Not the audience (do not market to them)
- VC-funded $1M+ ARR (they buy ChartMogul, want SLAs and integrations)
- Pre-revenue founders (no metrics yet, need customers first)
- Technical founders with SQL skills (they DIY in 1 hour)

---

## 3. Competitive landscape (May 2026)

The space is active but has a clear gap. Existing alternatives:

| Tool | Price | Source | Status |
|------|-------|--------|--------|
| ChartMogul | $99+/mo | Stripe-only effectively | Established |
| Baremetrics | $108+/mo | Stripe + a few | Established |
| ProfitWell | Free (sold to Paddle) | Stripe-focused | Acquired |
| [RevPilot](https://www.reddit.com/r/SaaS/comments/1rsz65q/) | Free / low | Stripe-only | Bootstrapped |
| [ProfitKit](https://profitkit.io) | Mid-tier | Stripe-only | Bootstrapped |
| turboboost.com | Free 90% | Stripe-only | New |
| Pulse (open source) | Free self-hosted | Stripe | Niche |
| **SubAudit** | **$9-19/mo** | **CSV, any source** | **Pre-launch** |

**Every competitor is Stripe-first.** SubAudit's CSV-first approach is the
strategic differentiator. Not a weakness — a positioning.

---

## 4. Why customers will pay (the actual answer)

Three reasons people will pay $9-19/mo, ordered by validated strength:

### 1. Price relief from the $100/mo prison
The single most-repeated complaint in our research. Founders below $20K MRR
view $99-130/mo analytics as gouging. $9 is "obviously yes" territory.

### 2. Works with my non-Stripe billing
ChartMogul and Baremetrics literally don't support these founders. SubAudit
takes any CSV. This is not a feature — it is the entire reason to exist.

### 3. Shows what Stripe hides
Voluntary vs involuntary churn split. Stripe blurs these. A founder seeing
*"40% of your churn is failed payments, not cancellations"* gets actionable
insight Stripe never gave.

**Note what is NOT on this list:** "investor-ready reports", "AI insights",
"forecasting accuracy". These are nice-to-have, not pay-to-have.

---

## 5. The 3 features that close the deal (v3.1-v3.3)

Full details in [SPEC.md §8](./SPEC.md#8-roadmap-priority-by-validated-pain).
Short version, ordered by ROI:

| # | Feature | Effort | Pain it addresses | Source |
|---|---------|--------|-------------------|--------|
| v3.1 | Voluntary vs Involuntary Churn | 1 day | "Stripe hides involuntary churn" | r/SaaS |
| v3.2 | Multi-source CSV presets | 2-3 days | "I don't use Stripe / I have manual invoices" | r/SaaS |
| v3.3 | Snapshot history | 2-3 days | "HubSpot can't tell me what MRR was last April" | r/hubspot |

Total: ~1 week of work. After this, SubAudit has a coherent story that maps
to specific complaints with specific URLs.

---

## 6. Go-to-market (zero budget edition)

### Phase 1 — Validation (weeks 1-2)
Goal: First 10 real signups. Find out what people actually do with the tool.

**Actions:**
1. Install PostHog free tier (1M events/mo). Without this we are blind.
2. Post on r/SaaS, r/indiehackers, r/microsaas. Format: *"I was tired of
   ChartMogul charging $129. Built a $9 alternative that works with any
   CSV (Paddle/Gumroad/Stripe/manual). Free to try, looking for feedback."*
3. Reply genuinely to existing complaint threads ("how do I track churn
   without Stripe?", "ChartMogul alternative?"). Do not spam.
4. List on [openalternative.co](https://openalternative.co) and similar
   "alternatives to" directories.

**Success criterion:** 10 people upload a CSV. Not signups — uploads.

### Phase 2 — Conversion (weeks 3-6)
Goal: First paying user.

**Actions:**
1. Ship v3.1 (involuntary churn split). Post about it: *"Stripe hides 40%
   of your churn. Here's how to see it."* This is a content-marketing post,
   not a launch.
2. Ship v3.2 (multi-source presets). Post in r/Paddle, r/Gumroad-adjacent
   communities. The angle is *"finally, analytics that don't require Stripe"*.
3. Add email capture (Buttondown free, 100 subs). For visitors who don't sign up.

**Success criterion:** 1 paying user. Yes, just one. That validates everything.

### Phase 3 — Scale or pivot (weeks 7-12)
Goal: $200 MRR or kill the project.

**Actions if traction:**
- Ship v3.3 (snapshot history) for retention
- Write one SEO post per week: "MRR vs ARR", "calculate churn correctly",
  "Paddle analytics guide"
- Apply to Product Hunt

**Actions if no traction:**
- Interview the 5 most engaged free users (we will have PostHog data by now)
- Reposition based on what they actually wanted
- Or shut down and apply lessons to the next project

---

## 7. What we explicitly will NOT do (yet)

These were in the old `PRODUCT_STRATEGY.md`. After Reddit research, none
of them are validated by real complaints. Drop them until proven needed.

- ❌ **Health Score** — nobody asked for it on Reddit
- ❌ **Industry benchmarks** — nice-to-have, not pay-to-have
- ❌ **Scheduled email reports** — no real complaints found
- ❌ **Public share links** — no real complaints found
- ❌ **Team / multi-seat** — no real complaints at this stage
- ❌ **Stripe OAuth integration** — too much engineering for unvalidated demand
- ❌ **Raising prices** — frozen until 10 paying users give feedback

---

## 8. Honest risks

1. **The space is crowded.** ProfitKit, RevPilot, turboboost, Pulse are all
   chasing the same gap. Differentiator must hold: non-Stripe focus.
2. **CSV-first is friction.** People want OAuth, not exports. Mitigation:
   one-click presets (v3.2) reduce friction to ~30 seconds.
3. **Streamlit is fragile.** 1 GB RAM = ~3-4 PRO sessions concurrent.
   This becomes a problem at $500 MRR, not before.
4. **Gumroad is not Stripe.** Some buyers don't trust Gumroad checkout.
   Mitigation: clearly state "30-day refund, no questions". Stripe migration
   triggered at $500 MRR.
5. **No marketing budget.** All growth must come from Reddit / IH / SEO /
   word of mouth for 6+ months. This is slow. Accept it.

---

## 9. The honest verdict

**SubAudit can plausibly hit $200-500 MRR within 6 months if:**
- The 3 roadmap features ship within 4 weeks
- 10+ Reddit posts go out without being spam
- The non-Stripe positioning is held consistently

**SubAudit will not hit $5K MRR in 12 months.** The strategy document this
file replaces claimed it could. That was optimistic by 3-5x for a solo
bootstrapped founder with no marketing budget. Plan accordingly.

**The minimum viable outcome is one paying user.** Everything below that
is hypothesis. Everything above is execution.
