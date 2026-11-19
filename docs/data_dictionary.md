# Data dictionary

All money values are Kenyan shillings (KES). All dates are ISO format (YYYY-MM-DD). Tables marked **real** are extracts from public reports; the rest are **synthetic**.

## Synthetic tables (`data/raw/synthetic/`)

### stores.csv
| Column | Description |
|--------|-------------|
| store_id | Primary key (S01 to S30) |
| store_name | Fictional store name |
| county_code, county | KNBS county code (1 to 47) and name; joins to `county_population_2019.csv` |
| format | Hypermarket, Supermarket or Mini-mart |
| catchment_type | Urban, Peri-urban or Town |
| floor_area_sqm | Floor area in square metres |
| opening_date | Date opened (before 2024) |
| price_level_index | Store price level relative to the base price (format and location effect) |

### products.csv
| Column | Description |
|--------|-------------|
| product_id | Primary key (P0001 to P0400) |
| sku | Stock-keeping unit code |
| product_name, brand, unit_size | Fictional brand names; brand multiplies the base price |
| category | One of 10 categories |
| base_price_kes, base_cost_kes | Price and cost at January 2024 prices |
| cpi_division | KNBS COICOP division whose index moves this product's price |
| price_anchor_source | "KNBS CPI release Table 3, national average" where the base price is anchored to a published average price, otherwise "Assumed (no public source)" |

### customers.csv
| Column | Description |
|--------|-------------|
| customer_id | Primary key (C00001 to C08000) |
| home_county_code, home_county | County of residence; customers shop at stores in their county |
| gender | F, M or Unspecified |
| age_band | 18-24, 25-34, 35-44, 45-54 or 55+ |
| loyalty_member | 1 if a loyalty member, else 0 |
| registration_date | Date registered (before 2024) |

### promotions.csv
| Column | Description |
|--------|-------------|
| promo_id | Primary key (PR01 to PR23) |
| promo_name, promo_type | Name and type (seasonal, category, storewide, loyalty payday) |
| start_date, end_date | Inclusive dates |
| discount_pct | Percent discount |
| categories | `ALL` for every category; otherwise the categories separated by `;` |
| loyalty_only | 1 if only loyalty members get it |
| anchor_event | Holiday or school-term event the promotion is tied to |

### transactions.csv
| Column | Description |
|--------|-------------|
| transaction_id | Primary key (T0000001...) |
| store_id | Foreign key to stores |
| customer_id | Foreign key to customers; **blank for walk-in customers** (about 35% of transactions) |
| transaction_date, transaction_time | Date and time of the sale |
| payment_method | Cash, M-Pesa, Airtel Money or Card |
| n_lines | Number of product lines |
| gross_kes, discount_kes, net_kes | Totals before discount, discount given, and amount paid |

### transaction_lines.csv
| Column | Description |
|--------|-------------|
| line_id | Primary key |
| transaction_id, product_id | Foreign keys |
| quantity | Units bought |
| unit_price_kes | Shelf price that month (base price × CPI division index × store price level) |
| unit_cost_kes | Unit cost that month (base cost × CPI division index) |
| discount_pct, discount_kes | Discount applied to the line |
| promo_id | Foreign key to promotions; blank if no promotion applied |
| line_net_kes | quantity × unit_price − discount |

### generation_log.json
Seed, parameters, row counts, file sizes and SHA-256 checksums of every file.

## Real tables (`data/raw/external/`)

### cpi_monthly_2024.csv
| Column | Description |
|--------|-------------|
| month | YYYY-MM; join key to sales (`transaction_date` truncated to month) |
| month_name | Month name |
| cpi_overall | KNBS overall CPI, base February 2019 = 100 |
| yoy_inflation_pct | Published year-on-year inflation |
| mom_change_pct_calc | Month-on-month change calculated from the index |
| cpi_in_own_release, yoy_in_own_release | Values in that month's own release (differ from the latest only for May 2024) |
| base_period, source | Base and source note |

### cpi_by_division_2024.csv
| Column | Description |
|--------|-------------|
| month | YYYY-MM |
| coicop_division | One of 13 divisions, plus "Total (all items)" |
| weight_pct | Basket weight |
| mom_change_pct, yoy_change_pct | Published monthly and annual % change |

### county_population_2019.csv
County code and name, total, male, female and intersex population, land area (sq km) and density, from the 2019 Census, Volume I. Totals sum to 47,564,296.

### payment_mix_by_county.csv
Share of adults (%) using banks, banks excluding mobile banking, and mobile money, for each county, from FinAccess 2021 (County Perspective).

### public_holidays_2024.csv
**Draft.** Date and name of 2024 public holidays, written from memory. `source_status` says to verify each date against the Kenya Gazette.
