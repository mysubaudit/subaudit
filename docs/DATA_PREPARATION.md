# Data Preparation Guide

**How to prepare your subscription data for SubAudit**

---

## Overview

SubAudit analyzes CSV files containing subscription transaction data. This guide explains:
- What data you need
- How to structure your CSV
- Common export sources
- Troubleshooting tips

---

## Required Columns

Your CSV must contain these four fields (column names can vary):

| Field | Description | Example Values |
|-------|-------------|----------------|
| **Customer ID** | Unique identifier for each customer | `cus_123`, `user_456`, `12345` |
| **Date** | Transaction or billing date | `2026-01-15`, `01/15/2026`, `2026-01-15 10:30:00` |
| **Amount** | Subscription price (numeric) | `29.99`, `49`, `199.00` |
| **Status** | Subscription state | `active`, `cancelled`, `paused`, `trialing` |

### Column Name Flexibility

SubAudit uses **fuzzy matching** to detect your columns automatically. These variations all work:

- **Customer ID:** `customer_id`, `user_id`, `subscriber_id`, `cust_id`, `id`
- **Date:** `date`, `transaction_date`, `billing_date`, `created_at`, `timestamp`
- **Amount:** `amount`, `price`, `mrr`, `revenue`, `total`
- **Status:** `status`, `state`, `subscription_status`, `plan_status`

If your column names are very different, you can manually map them in the **Column Mapping** step.

---

## Data Format Requirements

### Customer ID
- **Type:** Text or number
- **Uniqueness:** Each customer should have a consistent ID across all rows
- **Multi-row customers:** If a customer has multiple subscriptions, use the same ID for all their rows

✅ **Good:**
```
customer_id
cus_001
cus_001
cus_002
```

❌ **Bad:**
```
customer_id
cus_001
CUS_001  ← inconsistent capitalization
cus-002  ← inconsistent format
```

### Date
- **Format:** Any standard date format (ISO 8601, US, EU)
- **Accepted:** `YYYY-MM-DD`, `MM/DD/YYYY`, `DD/MM/YYYY`, `YYYY-MM-DD HH:MM:SS`
- **Timezone:** Not required (SubAudit treats all dates as same timezone)

✅ **Good:**
```
date
2026-01-15
2026-02-15
2026-03-15
```

❌ **Bad:**
```
date
January 15, 2026  ← text format
15-Jan-26         ← ambiguous
Q1 2026           ← not a date
```

### Amount
- **Type:** Numeric (integer or decimal)
- **Currency symbol:** Optional (will be stripped automatically)
- **Negative values:** Not allowed (use status to indicate refunds/cancellations)
- **Zero values:** Allowed (e.g., free trials)

✅ **Good:**
```
amount
29.99
49
0
$199.00  ← symbol is OK
```

❌ **Bad:**
```
amount
$29.99 USD  ← text after number
(49.00)     ← parentheses for negative
N/A         ← text instead of number
```

### Status
- **Type:** Text
- **Case-insensitive:** `active`, `Active`, `ACTIVE` all work
- **Common values:** `active`, `cancelled`, `canceled`, `paused`, `trialing`, `past_due`

✅ **Good:**
```
status
active
cancelled
paused
trialing
```

❌ **Bad:**
```
status
1           ← numeric code (use text)
true/false  ← boolean (use text)
```

---

## Data Structure

### One Row Per Subscription Per Month

SubAudit expects **one row for each customer for each month** they had an active subscription.

**Example:** Customer `cus_001` subscribed in January and stayed active through March:

```csv
customer_id,date,amount,status
cus_001,2026-01-15,29.99,active
cus_001,2026-02-15,29.99,active
cus_001,2026-03-15,29.99,active
```

### Handling Cancellations

When a customer cancels, include their **last active month** with status `cancelled`:

```csv
customer_id,date,amount,status
cus_001,2026-01-15,29.99,active
cus_001,2026-02-15,29.99,active
cus_001,2026-03-15,29.99,cancelled  ← last month before churn
```

**Do not include rows after cancellation** — absence in future months signals churn.

### Handling Pauses

If a customer pauses their subscription but doesn't churn, use status `paused`:

```csv
customer_id,date,amount,status
cus_001,2026-01-15,29.99,active
cus_001,2026-02-15,0,paused      ← paused, no charge
cus_001,2026-03-15,29.99,active  ← reactivated
```

SubAudit counts paused subscriptions as **retained** (not churned).

### Handling Upgrades/Downgrades

If a customer changes plans mid-month, include **one row per month** with the final amount:

```csv
customer_id,date,amount,status
cus_001,2026-01-15,29.99,active  ← Starter plan
cus_001,2026-02-15,49.99,active  ← Upgraded to Pro
cus_001,2026-03-15,49.99,active
```

SubAudit will detect the MRR change and calculate expansion revenue.

### Multiple Subscriptions Per Customer

If a customer has multiple active subscriptions, include **one row per subscription**:

```csv
customer_id,date,amount,status
cus_001,2026-01-15,29.99,active  ← Subscription A
cus_001,2026-01-15,19.99,active  ← Subscription B
cus_001,2026-02-15,29.99,active
cus_001,2026-02-15,19.99,active
```

SubAudit will sum amounts per customer per month automatically.

---

## Exporting from Common Platforms

### Stripe

1. Go to **Billing → Subscriptions**
2. Click **Export** (top right)
3. Select date range
4. Choose **CSV** format
5. Download and upload to SubAudit

**Stripe column mapping:**
- Customer ID → `customer`
- Date → `created` or `current_period_start`
- Amount → `plan.amount` (divide by 100 if in cents)
- Status → `status`

### Chargebee

1. Go to **Reports → Subscriptions**
2. Select date range
3. Click **Export to CSV**
4. Download and upload to SubAudit

**Chargebee column mapping:**
- Customer ID → `customer_id`
- Date → `activated_at` or `next_billing_at`
- Amount → `mrr`
- Status → `status`

### Recurly

1. Go to **Analytics → Subscriptions**
2. Select date range
3. Click **Export**
4. Choose **CSV** format
5. Download and upload to SubAudit

**Recurly column mapping:**
- Customer ID → `account_code`
- Date → `activated_at`
- Amount → `unit_amount`
- Status → `state`

### Paddle

1. Go to **Reports → Subscriptions**
2. Select date range
3. Click **Export CSV**
4. Download and upload to SubAudit

**Paddle column mapping:**
- Customer ID → `customer_id` or `user_id`
- Date → `subscription_created_at`
- Amount → `subscription_price`
- Status → `subscription_status`

### Gumroad

1. Go to **Sales → Subscribers**
2. Click **Export** (top right)
3. Choose **CSV** format
4. Download and upload to SubAudit

**Gumroad column mapping:**
- Customer ID → `Email` or `Buyer Email`
- Date → `Subscription Started` or `Created at`
- Amount → `Price` or `Recurrence Amount`
- Status → `Subscription Status`

### LemonSqueezy

1. Go to **Subscriptions** in your store dashboard
2. Click **Export CSV**
3. Select date range
4. Download and upload to SubAudit

**LemonSqueezy column mapping:**
- Customer ID → `customer_id` or `customer_email`
- Date → `created_at`
- Amount → `subtotal` or `total`
- Status → `status`

### Manual Spreadsheet

If you track subscriptions in Excel or Google Sheets:

1. Create columns: `customer_id`, `date`, `amount`, `status`
2. Fill one row per customer per month
3. Save as **CSV (Comma delimited)** (not `.xlsx`)
4. Upload to SubAudit

**Excel:** File → Save As → CSV (Comma delimited) (*.csv)
**Google Sheets:** File → Download → Comma Separated Values (.csv)

---

## Data Quality Checklist

Before uploading, verify:

- [ ] File is saved as `.csv` (not `.xlsx` or `.xls`)
- [ ] All required columns are present (customer_id, date, amount, status)
- [ ] Customer IDs are consistent (same format, no typos)
- [ ] Dates are in a standard format (YYYY-MM-DD recommended)
- [ ] Amounts are numeric (no text, no parentheses)
- [ ] All amounts use the same currency
- [ ] One row per customer per month
- [ ] No duplicate rows (same customer + same month)
- [ ] File size is within your plan limit (1K/10K/50K rows)

---

## Common Issues & Fixes

### Issue: "Could not detect required columns"

**Cause:** Column names don't match expected patterns.

**Fix:**
1. Check column names in your CSV (first row)
2. Rename columns to standard names: `customer_id`, `date`, `amount`, `status`
3. Or use the manual mapping step in SubAudit

### Issue: "Invalid date format"

**Cause:** Dates are in an unrecognized format.

**Fix:**
1. Open CSV in Excel/Google Sheets
2. Format date column as `YYYY-MM-DD` (e.g., `2026-01-15`)
3. Save as CSV and re-upload

### Issue: "Amount must be numeric"

**Cause:** Amount column contains text or special characters.

**Fix:**
1. Remove currency symbols: `$29.99` → `29.99`
2. Remove text: `$29.99 USD` → `29.99`
3. Replace blanks with `0` (for free trials)
4. Save and re-upload

### Issue: "File too large"

**Cause:** File exceeds your plan's row limit.

**Fix:**
- **Free plan:** Reduce to 1,000 rows or upgrade to Starter
- **Starter plan:** Reduce to 10,000 rows or upgrade to Pro
- **Pro plan:** Reduce to 50,000 rows or contact support

To reduce rows:
1. Filter to recent months only (e.g., last 12 months)
2. Remove cancelled customers from older periods
3. Aggregate multiple subscriptions per customer if possible

### Issue: "Duplicate rows detected"

**Cause:** Same customer appears multiple times in the same month.

**Fix:**
1. Check for duplicate entries in your source data
2. If customer has multiple subscriptions, keep all rows (SubAudit will sum them)
3. If truly duplicate, remove extra rows

### Issue: "Missing values in required columns"

**Cause:** Some rows have blank customer_id, date, amount, or status.

**Fix:**
1. Open CSV in Excel/Google Sheets
2. Filter for blank cells in required columns
3. Fill missing values or remove incomplete rows
4. Save and re-upload

---

## Example CSV Files

### Minimal Example (3 customers, 3 months)

```csv
customer_id,date,amount,status
cus_001,2026-01-15,29.99,active
cus_001,2026-02-15,29.99,active
cus_001,2026-03-15,29.99,active
cus_002,2026-01-20,49.99,active
cus_002,2026-02-20,49.99,cancelled
cus_003,2026-02-10,29.99,active
cus_003,2026-03-10,29.99,active
```

**Metrics this will produce:**
- MRR (March): $58.98 (cus_001 + cus_003)
- Churn Rate (Feb→Mar): 33% (1 of 3 customers churned)
- New MRR (Feb): $29.99 (cus_003 joined)

### Realistic Example (with upgrades, pauses, reactivations)

```csv
customer_id,date,amount,status
cus_001,2026-01-15,29.99,active
cus_001,2026-02-15,49.99,active
cus_001,2026-03-15,49.99,active
cus_002,2026-01-20,29.99,active
cus_002,2026-02-20,0,paused
cus_002,2026-03-20,29.99,active
cus_003,2026-01-10,49.99,active
cus_003,2026-02-10,49.99,cancelled
cus_004,2026-02-05,29.99,active
cus_004,2026-03-05,29.99,active
cus_005,2026-03-12,49.99,active
```

**Metrics this will produce:**
- MRR (March): $158.97
- Churn Rate (Feb→Mar): 25% (1 of 4 churned)
- NRR: >100% (cus_001 upgraded, cus_002 reactivated)
- New MRR (March): $49.99 (cus_005 joined)

---

## Need Help?

If you're stuck preparing your data:
1. Check the [FAQ](FAQ.md) for common questions
2. Email us at **biz.sardorbek@gmail.com** with:
   - A sample of your CSV (first 10 rows)
   - Description of your data source
   - What error you're seeing

We'll help you get your data ready for analysis.

---

**Ready to upload?** Go to [SubAudit](https://subaudit.streamlit.app) and start analyzing!
