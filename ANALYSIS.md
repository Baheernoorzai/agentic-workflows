# Expense Analytics

Analysis of `expenses.db` (50 expenses, 12 budgets) as seeded by `seed.py`.
Every figure below was recomputed a second way and reconciles (see
"How this was verified").

**Important:** the data is synthetic. It was generated from a fixed random seed,
so these findings describe this dataset, not real spending habits.

## The data

- Tables: `expenses(id, amount, category, date, note)` and
  `budgets(id, category, month, amount)`, unique on (category, month).
- 50 expenses, 2026-05-01 to 2026-09-29, 7 categories, 44 distinct days.
- 12 budgets: 6 for 2026-09 and 6 for 2026-10. No expenses dated October.
- Data quality checks were clean: no bad dates, no amounts at or below zero,
  no blank or case-duplicate categories, no duplicate rows, no id gaps.

Money is summed in whole cents (`CAST(ROUND(amount*100) AS INTEGER)`) so float
rounding cannot affect the totals.

## Questions

1. Q1: Where does the money go? Spend per category and its share of the total.
2. Q2: How is spending trending month over month?
3. Q3: What are the biggest single expenses?
4. Q5: How did September actual spend compare with budget?

Not answered yet: Q4 (average expense per category) and Q6 (month to month
variability per category).

## Q1. Total spend per category

```sql
WITH e AS (SELECT id, category, date, note, substr(date,1,7) AS month,
                  CAST(ROUND(amount*100) AS INTEGER) AS cents FROM expenses),
t AS (SELECT SUM(cents) AS all_c,
             SUM(CASE WHEN category <> 'Rent' THEN cents END) AS nonrent_c FROM e)
SELECT category, COUNT(*) AS expenses, SUM(cents)/100.0 AS total,
       ROUND(100.0*SUM(cents)/t.all_c, 1) AS pct_of_all,
       CASE WHEN category <> 'Rent'
            THEN ROUND(100.0*SUM(cents)/t.nonrent_c, 1) END AS pct_excl_rent
FROM e, t GROUP BY category ORDER BY total DESC;
```

| Category | Expenses | Total | Share of all | Share excluding Rent |
|---|---|---|---|---|
| Rent | 5 | 6,000.00 | 68.8% | n/a |
| Groceries | 9 | 704.97 | 8.1% | 25.9% |
| Utilities | 7 | 632.30 | 7.3% | 23.3% |
| Transport | 10 | 379.59 | 4.4% | 14.0% |
| Health | 6 | 347.38 | 4.0% | 12.8% |
| Entertainment | 8 | 339.47 | 3.9% | 12.5% |
| Dining | 5 | 315.84 | 3.6% | 11.6% |

Grand totals: all spend 8,719.55, Rent 6,000.00, everything else 2,719.55.

## Q2. Month over month trend

```sql
WITH e AS (SELECT category, substr(date,1,7) AS month,
                  CAST(ROUND(amount*100) AS INTEGER) AS cents FROM expenses),
m AS (SELECT month, COUNT(*) AS n, SUM(cents) AS all_c,
             SUM(CASE WHEN category<>'Rent' THEN cents ELSE 0 END) AS ex_c
      FROM e GROUP BY month)
SELECT month, n AS expenses, all_c/100.0 AS total,
       ROUND(100.0*(all_c - LAG(all_c) OVER (ORDER BY month))
             / LAG(all_c) OVER (ORDER BY month), 1) AS pct_change,
       ex_c/100.0 AS excl_rent,
       ROUND(100.0*(ex_c - LAG(ex_c) OVER (ORDER BY month))
             / LAG(ex_c) OVER (ORDER BY month), 1) AS pct_change_excl_rent
FROM m ORDER BY month;
```

| Month | Expenses | Total | Change | Excluding Rent | Change |
|---|---|---|---|---|---|
| 2026-05 | 12 | 1,860.46 | | 660.46 | |
| 2026-06 | 10 | 1,807.90 | -2.8% | 607.90 | -8.0% |
| 2026-07 | 11 | 1,748.44 | -3.3% | 548.44 | -9.8% |
| 2026-08 | 8 | 1,646.40 | -5.8% | 446.40 | -18.6% |
| 2026-09 | 9 | 1,656.35 | +0.6% | 456.35 | +2.2% |

## Q3. Biggest single expenses

```sql
-- ten biggest overall
SELECT date, category, cents/100.0 AS amount, COALESCE(note,'') AS note
FROM e ORDER BY cents DESC, date LIMIT 10;

-- five biggest excluding Rent
SELECT date, category, cents/100.0 AS amount, COALESCE(note,'') AS note
FROM e WHERE category <> 'Rent' ORDER BY cents DESC, date LIMIT 5;
```

(`e` is the same cents CTE as in Q1.)

The top five overall are the five Rent payments of 1,200.00. Excluding Rent:

| Date | Category | Amount | Note |
|---|---|---|---|
| 2026-07-09 | Utilities | 158.74 | Internet |
| 2026-07-07 | Groceries | 117.05 | |
| 2026-05-30 | Health | 105.44 | Gym |
| 2026-05-13 | Groceries | 105.42 | Weekly shop |
| 2026-06-24 | Utilities | 104.71 | |

## Q5. September 2026: actual spend versus budget

```sql
WITH e AS (SELECT category, substr(date,1,7) AS month,
                  CAST(ROUND(amount*100) AS INTEGER) AS cents FROM expenses),
s AS (SELECT category, SUM(cents) AS spent FROM e
      WHERE month = '2026-09' GROUP BY category),
b AS (SELECT category, CAST(ROUND(amount*100) AS INTEGER) AS bud
      FROM budgets WHERE month = '2026-09'),
cats AS (SELECT category FROM s UNION SELECT category FROM b)
SELECT cats.category, b.bud/100.0 AS budget, COALESCE(s.spent,0)/100.0 AS spent,
       (b.bud - COALESCE(s.spent,0))/100.0 AS remaining,
       CASE WHEN b.bud IS NULL THEN 'no budget'
            WHEN COALESCE(s.spent,0) > b.bud THEN 'OVER' ELSE 'within' END AS status
FROM cats LEFT JOIN s ON s.category=cats.category
          LEFT JOIN b ON b.category=cats.category
ORDER BY (COALESCE(s.spent,0) > COALESCE(b.bud, 1e18)) DESC, cats.category;
```

| Category | Budget | Spent | Remaining | Status |
|---|---|---|---|---|
| Groceries | 50.00 | 59.30 | -9.30 | OVER |
| Transport | 90.00 | 91.31 | -1.31 | OVER |
| Dining | 100.00 | 79.79 | 20.21 | within |
| Entertainment | none | 61.60 | n/a | no budget |
| Health | 100.00 | 0.00 | 100.00 | within |
| Rent | 1,200.00 | 1,200.00 | 0.00 | within (exactly at budget) |
| Utilities | 200.00 | 164.35 | 35.65 | within |

September total budget: 1,740.00. September total spend: 1,656.35.

## Insights (verified)

- **Rent is about 69% of all spending.** It is a fixed 1,200 a month, so the
  real room to save is in the remaining 31% (2,719.55 over five months).
- **Groceries and Utilities are the biggest everyday costs.** Together they
  make up about half of non-rent spending (49%).
- **Everyday spending has fallen.** Excluding Rent, monthly spend dropped from
  about 660 in May to about 456 in September, roughly 31% lower. It ticked up
  slightly (+2%) in September after the August low.
- **No single everyday purchase is large.** The biggest non-rent expense is
  158.74 (an internet bill), only 5.8% of non-rent spending. The median
  non-rent expense is 53.20, across 45 expenses.
- **September stayed under budget in total, but two categories went over.**
  Spending in budgeted categories was 1,594.75 against 1,740 budgeted.
  Groceries was over by 9.30 and Transport by 1.31. A further 61.60 went to
  Entertainment, which has no budget.

## How this was verified

Every figure above was recomputed independently: the raw rows were read with a
plain `SELECT` and re-summed in Python using `Decimal`, with no SQL
aggregation. The app's own `monthly_report` (grand total and all five monthly
totals) and the `/budgets?month=2026-09` page (exactly two OVER flags) were
also compared. 32 checks, all matching.

## Caveats

- The data is synthetic (seeded random), so findings describe this dataset only.
- The September budgets were chosen to demonstrate the budget feature. That
  Groceries and Transport are over budget is by design, not a finding about
  spending behavior.
- The sample is small: 50 expenses over 5 months, and August has only 8. The
  falling trend is worth watching but is not firm.
- October has budgets but no expenses. May to August have no budgets.
