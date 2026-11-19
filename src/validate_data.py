#!/usr/bin/env python3
"""
validate_data.py - integrity checks on data/raw/ (standard library only).

Run after generate_data.py:   python src/validate_data.py
Exits with status 1 if any check fails.
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYN = ROOT / "data" / "raw" / "synthetic"
EXT = ROOT / "data" / "raw" / "external"

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


stores, products = read(SYN / "stores.csv"), read(SYN / "products.csv")
customers, promos = read(SYN / "customers.csv"), read(SYN / "promotions.csv")
txns, lines = read(SYN / "transactions.csv"), read(SYN / "transaction_lines.csv")
cpi = read(EXT / "cpi_monthly_2024.csv")
pop = read(EXT / "county_population_2019.csv")

# size ranges required by the brief
check("stores between 25 and 40", 25 <= len(stores) <= 40, len(stores))
check("counties with stores between 10 and 15", 10 <= len({s["county"] for s in stores}) <= 15,
      len({s["county"] for s in stores}))
check("products between 300 and 500", 300 <= len(products) <= 500, len(products))
check("categories between 8 and 10", 8 <= len({p["category"] for p in products}) <= 10)
check("customers between 5,000 and 10,000", 5000 <= len(customers) <= 10000, len(customers))

# keys unique
for name, rows, key in [("stores", stores, "store_id"), ("products", products, "product_id"),
                        ("customers", customers, "customer_id"), ("promotions", promos, "promo_id"),
                        ("transactions", txns, "transaction_id"), ("lines", lines, "line_id")]:
    check(f"{name}.{key} is unique", len({r[key] for r in rows}) == len(rows))

# foreign keys
sid, pid = {s["store_id"] for s in stores}, {p["product_id"] for p in products}
cid, prid = {c["customer_id"] for c in customers}, {p["promo_id"] for p in promos}
tid = {t["transaction_id"] for t in txns}
check("transactions -> stores", all(t["store_id"] in sid for t in txns))
check("transactions -> customers (blank = walk-in)", all(t["customer_id"] in cid or t["customer_id"] == "" for t in txns))
check("lines -> transactions", all(l["transaction_id"] in tid for l in lines))
check("lines -> products", all(l["product_id"] in pid for l in lines))
check("lines -> promotions (blank = none)", all(l["promo_id"] in prid or l["promo_id"] == "" for l in lines))
codes = {int(p["county_code"]) for p in pop}
check("stores/customers use valid county codes",
      all(int(s["county_code"]) in codes for s in stores) and all(int(c["home_county_code"]) in codes for c in customers))

# values
check("quantities >= 1", all(int(l["quantity"]) >= 1 for l in lines))
check("prices > 0", all(float(l["unit_price_kes"]) > 0 for l in lines))
check("discounts never exceed 25%", all(float(l["discount_pct"]) <= 25 for l in lines))
check("payment methods are the four expected", {t["payment_method"] for t in txns} ==
      {"Cash", "M-Pesa", "Airtel Money", "Card"})

# reconciliation: line totals = transaction totals
line_sum = defaultdict(float)
for l in lines:
    line_sum[l["transaction_id"]] += float(l["line_net_kes"])
worst = max(abs(line_sum[t["transaction_id"]] - float(t["net_kes"])) for t in txns)
check("sum of line_net_kes equals transaction net_kes", worst < 0.05, f"max gap {worst:.3f} KES")
check("every transaction has at least one line", all(t["transaction_id"] in line_sum for t in txns))

# dates and CPI join
months = {t["transaction_date"][:7] for t in txns}
cpi_months = {r["month"] for r in cpi}
check("all transactions fall in 2024", all(t["transaction_date"].startswith("2024") for t in txns))
check("every sales month has a CPI row (12/12)", months == cpi_months, f"{len(months)} months")

# reproducibility log
log = json.load(open(SYN / "generation_log.json"))
check("generation log marks data as synthetic", log.get("synthetic") is True, f"seed {log['seed']}")

# file sizes (GitHub warns at 50 MB)
biggest = max(p.stat().st_size for p in SYN.glob("*.csv")) / 1e6
check("largest CSV under 50 MB", biggest < 50, f"{biggest:.1f} MB")

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
