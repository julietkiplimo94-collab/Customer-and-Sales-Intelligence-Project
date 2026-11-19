# Problem Statement: Customer and Sales BI for a Kenyan Retail Chain

**Project:** Customer and Sales BI capstone
**Author:** Juliet Kiplimo
**Data:** Synthetic transactions for a fictional chain ("Soko Fresh"), joined to real KNBS CPI, Census and FinAccess data. See the [README](../README.md) for what is real and what is simulated.

---

## 1. Business context

Soko Fresh is a fictional supermarket chain with **30 stores in 12 Kenyan counties** (hypermarkets, supermarkets and mini-marts), about **400 products in 10 grocery and household categories**, and **8,000 identified customers**, nearly half of them loyalty members. The dataset covers **January to December 2024**.

Through 2024 Kenyan inflation fell from 6.9% to 3.0% (KNBS), while food prices kept rising, though more slowly. Mobile money use is widespread but differs sharply between counties: in the 2021 FinAccess survey 93.9% of adults in Nairobi used it, against 60.7% in Garissa. Management has to decide on pricing, promotions and store expansion without knowing how much of its sales movement comes from the market and how much from its own decisions.

## 2. Problem statement

> Soko Fresh lacks a single, reliable view of how sales, margin, promotions and payment methods change across stores, counties and months, and how those changes relate to national price inflation. Without it, management cannot tell which promotions earn their discount, which stores and categories carry the margin, how customers pay, or which county to open in next.

The project builds that view: a clean data model, a CPI-linked analysis and a BI dashboard that answers the questions below.

## 3. Business questions

| ID | Business question | Data used |
|----|-------------------|-----------|
| BQ1 | **Where do revenue and gross margin come from?** Which stores, counties, formats and categories earn the most, and which dilute margin? | transactions, transaction_lines, products, stores |
| BQ2 | **How do prices and volumes move with inflation?** How closely do shelf prices follow the KNBS CPI by division, and how much do units sold fall when prices rise, by category? | transaction_lines, products, KNBS CPI (overall and by division) |
| BQ3 | **Which promotions pay back?** Does each promotion earn more extra margin than the discount it gives away? | promotions, transaction_lines, products |
| BQ4 | **How do customers pay, and does it shift?** What is the mix of M-Pesa, Airtel Money, cash and card by county, store format and month, and how does it relate to county mobile money use and to inflation? | transactions, stores, FinAccess county rates, CPI |
| BQ5 | **Are loyalty members worth more?** How do visits, basket size and spend differ between loyalty members, other identified customers and walk-ins? | customers, transactions |
| BQ6 | **When do customers shop?** How much do paydays, weekends and public holidays lift traffic and basket value? | transactions, public holidays |
| BQ7 | **What drives the basket?** Which categories and products make up most sales, and which categories are bought together? | transaction_lines, products |
| BQ8 | **Where should the chain open next?** Which counties without a store have the most people and the highest mobile money use, and how does sales per resident compare in counties with stores? | county population, FinAccess rates, stores, transactions |

## 4. Success measures

### 4.1 Business measures reported on the dashboard

| ID | Measure | Definition | What counts as answering the question |
|----|---------|------------|---------------------------------------|
| BQ1 | Net sales, gross margin %, average basket (KES), transactions | Net sales = sum of `line_net_kes`. Gross margin % = (net sales − units × `unit_cost_kes`) / net sales | Figures by store, county, format, category and month, with the top 5 and bottom 5 stores by margin %. Dashboard totals equal the transaction totals (gap of 0 KES) |
| BQ2 | Price index vs KNBS index; elasticity by category | Monthly average shelf price relative to January, compared with the KNBS division index (Jan = 1.0). Elasticity = % change in units per % change in price | Correlation with the KNBS series reported for each division. An elasticity with a 95% interval for each of the 10 categories. All 12 months joined to CPI |
| BQ3 | Promotion ROI | (Extra gross margin vs a baseline period − discount given) / discount given, using the same stores and categories before or after the promotion | Every promotion ranked by ROI. Promotions with ROI below 0 flagged, with a recommendation to repeat, change or drop each |
| BQ4 | Payment shares; digital share | Share of transactions by payment method. Digital share = M-Pesa + Airtel Money + card | Payment shares by county, format and month. Correlation between county mobile money use and digital share. Trend in cash share across 2024 compared with inflation |
| BQ5 | Spend per customer; loyalty gap | Annual net sales per identified customer; visits per customer; average basket | Loyalty vs non-loyalty difference in spend, visits and basket with a confidence interval. Share of linked sales from the top 20% of customers |
| BQ6 | Calendar lift | Average daily transactions and basket on payday weeks, weekends and holidays vs ordinary days | Lift percentages for each day type, with a short recommendation for stock and staffing |
| BQ7 | Category mix; SKU concentration; basket pairs | Category share of net sales. Share of sales from the top 20% of SKUs. Lift of category pairs | Top categories, a concentration figure, and the top 5 category pairs by lift |
| BQ8 | Sales per 1,000 residents; expansion score | Sales per 1,000 residents in counties with stores. Score for the other counties = population × mobile money use | A ranked shortlist of 3 counties to open in, with the reasoning |

### 4.2 Project acceptance criteria

| Criterion | Target | How it is checked |
|-----------|--------|-------------------|
| Required dataset | Stores, products, categories, customers, 12 months of transactions with promotions and payment methods, and one public context source joined to sales | `python src/validate_data.py` (27 checks) |
| Data integrity | Every key is unique and every foreign key resolves; line totals equal transaction totals | `validate_data.py` |
| CPI join | 12 of 12 sales months matched to KNBS CPI | `validate_data.py` |
| Reproducibility | Re-running `generate_data.py` with seed 42 gives identical file checksums | `data/raw/synthetic/generation_log.json` |
| Transparency | Dataset labelled as synthetic; real and simulated parts named; every source listed with terms | README and `docs/data_inventory.xlsx` |
| Portability | No absolute or `J:\` paths; notebooks read from `data/raw/` | Search the repository for `J:\` |
| Repository size | Each file under 50 MB | `validate_data.py` |

## 5. Scope

**In scope:** the six simulated tables, the real CPI, population and payment-usage tables, data validation, exploratory and CPI-linked analysis, and a dashboard.

**Out of scope:** forecasting, real customer data, online sales, supplier data and stock levels.

## 6. Limitations the analysis must state

1. **The sales data is synthetic.** It follows assumptions written in `src/generate_data.py`: prices follow the KNBS division index, units respond to price with assumed elasticities, discounts lift units, and payment shares depend on county mobile money and bank use. If the analysis recovers these relationships, it shows the method works. It is not evidence about real shoppers.
2. **CPI is national.** KNBS collects prices in urban centres, so it does not describe every county. Division indices are chained from published one-decimal monthly changes, so small rounding drift is possible.
3. **Year gap.** County mobile money and bank rates are from the 2021 survey and sales are for 2024.
4. **Draft holiday calendar.** The holiday dates were written from memory and must be checked against the Kenya Gazette before final submission.
5. **Sample scale.** 60,000 transactions is a sample, not the full volume of a 30-store chain, so absolute sales figures are illustrative.
