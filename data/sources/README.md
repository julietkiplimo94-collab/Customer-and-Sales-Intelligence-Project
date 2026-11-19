# Original source files (not committed)

The PDFs below were used to extract the tables in `data/raw/external/`. They are git-ignored because most state no reuse licence. Download them again from the URLs in `docs/data_inventory.xlsx` and keep them in this folder.

| File | Used for | Extracted to |
|------|----------|--------------|
| `Kenya-Consumer-Price-Indices-and-Inflation-Rates-<Month>-2024.pdf` (12 files) | Overall CPI and CPI by COICOP division | `cpi_monthly_2024.csv`, `cpi_by_division_2024.csv` |
| `2019-Kenya-population-and-Housing-Census-Volume-1-Population-By-County-And-Sub-County.pdf` | County populations | `county_population_2019.csv` |
| `2021-FinAccess-Household-Survey-County-Pespective.pdf` | County mobile money and bank usage | `payment_mix_by_county.csv` |
| `2021-FinAccess-Household-Survey.pdf` | National cash vs non-cash shares | Assumptions in `src/generate_data.py` |
| `Sector_Statistics_Report_Q1_2024-2025.pdf` (Communications Authority) | M-Pesa and Airtel Money share of mobile money subscriptions | Assumption `MPESA_SHARE_OF_MOBILE` in `src/generate_data.py` |
