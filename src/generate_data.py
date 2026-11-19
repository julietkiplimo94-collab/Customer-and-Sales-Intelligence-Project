#!/usr/bin/env python3
"""
generate_data.py - build the SYNTHETIC retail tables for the capstone.

What is real and what is simulated
----------------------------------
REAL (read from data/raw/external/, extracted from public sources):
  - KNBS monthly CPI, overall and by COICOP division, 2024
  - KNBS 2019 Census county populations
  - FinAccess 2021 county mobile-money and bank usage rates

SIMULATED (written to data/raw/synthetic/):
  stores, products, customers, promotions, transactions, transaction_lines
  Every row of these six tables is invented by this script. Nothing in them
  is a record of a real retailer, shopper or sale.

Relationships that are built in (all are ASSUMPTIONS, see the CONFIG block)
-------------------------------------------------------------------------
  1. Shelf prices follow the real KNBS division index month by month.
  2. Units bought respond to price with a per-category elasticity.
  3. Discounts lift units sold.
  4. The payment mix depends on county mobile-money and bank usage, store
     format, catchment type and (slightly) on inflation.
Anything an analysis "finds" about these relationships was put there by the
assumptions below. It is not evidence about the real Kenyan market.

Reproducibility
---------------
Uses only the Python standard library and a seeded random.Random, so the same
seed and parameters give identical files. A checksum log is written next to
the data (data/raw/synthetic/generation_log.json).

Usage
-----
    python src/generate_data.py                      # defaults: seed 42
    python src/generate_data.py --seed 7 --transactions 80000
"""
import argparse
import csv
import hashlib
import json
import math
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "data" / "raw" / "external"
OUT = ROOT / "data" / "raw" / "synthetic"

# ----------------------------------------------------------------------------
# CONFIG - every number below is an assumption unless a comment says otherwise
# ----------------------------------------------------------------------------
YEAR = 2024  # matches the KNBS CPI files loaded in data/raw/external

# Stores: (county, [(format, location), ...], catchment type)
STORE_PLAN = [
    ("Nairobi", [("Hypermarket", "Westlands"), ("Hypermarket", "Embakasi"), ("Supermarket", "Kilimani"),
                 ("Supermarket", "Kasarani"), ("Supermarket", "Karen"), ("Mini-mart", "Langata"),
                 ("Mini-mart", "Donholm")], "Urban"),
    ("Mombasa", [("Hypermarket", "Nyali"), ("Supermarket", "Mvita"), ("Supermarket", "Bamburi"),
                 ("Mini-mart", "Likoni")], "Urban"),
    ("Kiambu", [("Hypermarket", "Thika"), ("Supermarket", "Ruiru"), ("Mini-mart", "Limuru")], "Peri-urban"),
    ("Nakuru", [("Hypermarket", "Nakuru Town"), ("Supermarket", "Naivasha"), ("Mini-mart", "Gilgil")], "Urban"),
    ("Kisumu", [("Hypermarket", "Kisumu CBD"), ("Supermarket", "Milimani")], "Urban"),
    ("Uasin Gishu", [("Supermarket", "Eldoret CBD"), ("Mini-mart", "Langas")], "Urban"),
    ("Machakos", [("Supermarket", "Machakos Town"), ("Mini-mart", "Athi River")], "Peri-urban"),
    ("Kajiado", [("Supermarket", "Kitengela"), ("Mini-mart", "Ngong")], "Peri-urban"),
    ("Nyeri", [("Supermarket", "Nyeri Town"), ("Mini-mart", "Karatina")], "Town"),
    ("Meru", [("Supermarket", "Meru Town")], "Town"),
    ("Kakamega", [("Supermarket", "Kakamega Town")], "Town"),
    ("Garissa", [("Mini-mart", "Garissa Town")], "Town"),
]
FORMAT_TRAFFIC_WEIGHT = {"Hypermarket": 3.0, "Supermarket": 1.5, "Mini-mart": 0.6}
FORMAT_LINES_LAMBDA = {"Hypermarket": 3.0, "Supermarket": 2.0, "Mini-mart": 1.0}  # extra lines per basket
FORMAT_PRICE_FACTOR = {"Hypermarket": 0.97, "Supermarket": 1.00, "Mini-mart": 1.05}
FORMAT_CARD_MULT = {"Hypermarket": 1.3, "Supermarket": 1.0, "Mini-mart": 0.5}
FORMAT_AREA_SQM = {"Hypermarket": (3000, 5000), "Supermarket": (1200, 2500), "Mini-mart": (300, 700)}
CATCHMENT_CASH_ADJ = {"Urban": 0.00, "Peri-urban": 0.02, "Town": 0.04}

# Payment mix (all assumptions; county inputs are real FinAccess 2021 rates)
CASH_BASE = 0.60              # cash share when mobile money usage is 0%
CASH_DIGITAL_SLOPE = 0.35     # cash share falls by this much per 1.0 of mobile-money usage
CARD_BASE = 0.02
CARD_BANK_SLOPE = 0.25        # card share rises with bank usage excluding mobile banking
CASH_INFLATION_SENSITIVITY = 1.5   # +1 pt of YoY inflation above the mean adds 1.5 pts to cash share
MPESA_SHARE_OF_MOBILE = 92.3 / (92.3 + 7.6)  # Communications Authority Q1 FY24/25, share of subscriptions

# Categories: share of basket lines, count of SKUs, gross margin, price elasticity (assumed),
# the KNBS COICOP division whose index moves its prices, and brands to use.
FOOD = "Food and Non-Alcoholic Beverages"
PERSONAL = "Personal Care, Social Protection and Miscellaneous Goods and Services"
HOUSEHOLD = "Furnishings, Household Equipment and Routine Household Maintenance"
KNBS = "KNBS CPI release Table 3, national average"
ASSUMED = "Assumed (no public source)"
CATEGORIES = {
    "Maize flour & grains": dict(share=0.14, n=44, margin=0.12, elast=-0.30, div=FOOD, nbrand=8, items=[
        ("Maize flour (sifted)", "2 kg", 156.11, KNBS), ("Maize flour (fortified)", "2 kg", 175.32, KNBS),
        ("Maize flour (loose-style)", "1 kg", 75.31, KNBS), ("Wheat flour (white)", "2 kg", 200.41, KNBS),
        ("Rice (white)", "2 kg", 459.79, KNBS), ("Beans", "1 kg", 185.96, KNBS)]),
    "Cooking oil & fats": dict(share=0.08, n=32, margin=0.10, elast=-0.40, div=FOOD, nbrand=7, items=[
        ("Cooking oil", "1 L", 320.0, ASSUMED), ("Cooking oil", "3 L", 900.0, ASSUMED),
        ("Cooking oil", "500 ml", 170.0, ASSUMED), ("Cooking fat", "1 kg", 330.0, ASSUMED),
        ("Margarine", "500 g", 250.0, ASSUMED)]),
    "Sugar & sweeteners": dict(share=0.07, n=26, margin=0.09, elast=-0.50, div=FOOD, nbrand=7, items=[
        ("Sugar", "1 kg", 209.55, KNBS), ("Sugar", "2 kg", 410.0, ASSUMED),
        ("Brown sugar", "1 kg", 235.0, ASSUMED), ("Honey", "500 g", 480.0, ASSUMED)]),
    "Dairy & eggs": dict(share=0.12, n=48, margin=0.18, elast=-0.50, div=FOOD, nbrand=7, items=[
        ("Fresh milk", "500 ml", 57.42, KNBS), ("Fresh milk", "1 L", 110.0, ASSUMED),
        ("Long-life milk", "500 ml", 75.0, ASSUMED), ("Yoghurt", "500 ml", 120.0, ASSUMED),
        ("Butter", "250 g", 330.0, ASSUMED), ("Eggs", "tray of 30", 430.0, ASSUMED),
        ("Cheese", "200 g", 380.0, ASSUMED), ("Cream", "250 ml", 200.0, ASSUMED)]),
    "Beverages": dict(share=0.11, n=50, margin=0.25, elast=-0.80, div=FOOD, nbrand=7, items=[
        ("Tea leaves", "250 g", 130.0, ASSUMED), ("Coffee", "100 g", 280.0, ASSUMED),
        ("Soda", "500 ml", 70.0, ASSUMED), ("Fruit juice", "1 L", 180.0, ASSUMED),
        ("Bottled water", "1.5 L", 90.0, ASSUMED), ("Energy drink", "300 ml", 120.0, ASSUMED),
        ("Drinking chocolate", "250 g", 260.0, ASSUMED), ("Instant porridge", "500 g", 190.0, ASSUMED)]),
    "Fresh produce": dict(share=0.14, n=52, margin=0.30, elast=-0.40, div=FOOD, nbrand=5, items=[
        ("Tomatoes", "1 kg", 91.17, KNBS), ("Onions", "1 kg", 150.40, KNBS), ("Potatoes", "1 kg", 100.21, KNBS),
        ("Cabbage", "1 kg", 60.52, KNBS), ("Kale (sukuma wiki)", "1 kg", 63.19, KNBS),
        ("Carrots", "1 kg", 108.14, KNBS), ("Oranges", "1 kg", 86.87, KNBS), ("Mangoes", "1 kg", 99.76, KNBS),
        ("Spinach", "1 kg", 73.65, KNBS), ("Bananas", "1 kg", 80.0, ASSUMED), ("Avocado", "1 kg", 95.0, ASSUMED)]),
    "Bread & bakery": dict(share=0.06, n=30, margin=0.22, elast=-0.30, div=FOOD, nbrand=7, items=[
        ("Bread", "400 g", 60.0, ASSUMED), ("Bread", "800 g", 110.0, ASSUMED), ("Buns", "pack of 6", 90.0, ASSUMED),
        ("Chapati", "pack of 5", 100.0, ASSUMED), ("Mandazi", "pack of 6", 80.0, ASSUMED)]),
    "Toiletries & personal care": dict(share=0.10, n=52, margin=0.30, elast=-0.70, div=PERSONAL, nbrand=6, items=[
        ("Bar soap", "200 g", 90.0, ASSUMED), ("Body lotion", "400 ml", 380.0, ASSUMED),
        ("Toothpaste", "100 ml", 210.0, ASSUMED), ("Toothbrush", "each", 120.0, ASSUMED),
        ("Shampoo", "400 ml", 350.0, ASSUMED), ("Roll-on deodorant", "50 ml", 230.0, ASSUMED),
        ("Sanitary pads", "pack of 10", 150.0, ASSUMED), ("Toilet paper", "4 rolls", 260.0, ASSUMED),
        ("Petroleum jelly", "250 g", 280.0, ASSUMED)]),
    "Household cleaning": dict(share=0.08, n=34, margin=0.28, elast=-0.60, div=HOUSEHOLD, nbrand=5, items=[
        ("Laundry powder", "1 kg", 330.0, ASSUMED), ("Liquid detergent", "1 L", 420.0, ASSUMED),
        ("Dish soap", "750 ml", 250.0, ASSUMED), ("Bleach", "750 ml", 190.0, ASSUMED),
        ("Floor cleaner", "1 L", 300.0, ASSUMED), ("Laundry bar soap", "800 g", 280.0, ASSUMED),
        ("Air freshener", "300 ml", 330.0, ASSUMED), ("Sponges", "pack of 3", 100.0, ASSUMED)]),
    "Snacks & confectionery": dict(share=0.10, n=32, margin=0.30, elast=-1.00, div=FOOD, nbrand=6, items=[
        ("Biscuits", "250 g", 120.0, ASSUMED), ("Crisps", "100 g", 80.0, ASSUMED),
        ("Chocolate bar", "100 g", 180.0, ASSUMED), ("Sweets", "200 g", 100.0, ASSUMED),
        ("Peanuts", "200 g", 130.0, ASSUMED), ("Popcorn", "100 g", 90.0, ASSUMED),
        ("Cookies", "150 g", 140.0, ASSUMED)]),
}
# Fictional brands (any resemblance to real products is accidental); price multiplier is drawn per brand
BRANDS = ["Kijani", "Savanna Gold", "Mama Pima", "Rift Valley Best", "Jua Fresh", "Baraka", "Zawadi",
          "Kilele", "Tamu", "Safi Choice", "Pwani Select", "Nyota", "Soko Fresh Own Label"]
OWN_LABEL = "Soko Fresh Own Label"

PROMO_LIFT = 1.5          # units multiplier = 1 + PROMO_LIFT * discount_fraction
UNITS_LAMBDA = 0.9        # base extra units per line (units = 1 + Poisson)
SHARE_LINKED_TXNS = 0.65  # share of transactions tied to an identified customer
LOYALTY_RATE = 0.45       # share of identified customers who are loyalty members
HOUR_WEIGHTS = {8: 1, 9: 2, 10: 3, 11: 4, 12: 5, 13: 6, 14: 5, 15: 4, 16: 4, 17: 5, 18: 6, 19: 5, 20: 3}

# Promotions (dates are 2024). categories "ALL" or a list. Based on the holiday calendar and school terms.
def promo_plan():
    P = []
    def add(name, ptype, start, end, pct, cats, loyalty_only=0, holiday=""):
        P.append(dict(promo_name=name, promo_type=ptype, start_date=start, end_date=end,
                      discount_pct=pct, categories=cats, loyalty_only=loyalty_only, anchor_event=holiday))
    add("New Year Staples", "Seasonal percent-off", "2024-01-01", "2024-01-14", 10,
        ["Maize flour & grains", "Cooking oil & fats", "Sugar & sweeteners"], 0, "New Year / school opening")
    add("Ramadan Essentials", "Seasonal percent-off", "2024-03-11", "2024-04-10", 8,
        ["Cooking oil & fats", "Sugar & sweeteners", "Dairy & eggs", "Beverages"], 0, "Ramadan / Eid-ul-Fitr")
    add("Easter Baking Deal", "Seasonal percent-off", "2024-03-25", "2024-04-01", 12,
        ["Sugar & sweeteners", "Dairy & eggs", "Bread & bakery"], 0, "Easter")
    add("Labour Day Weekend", "Seasonal percent-off", "2024-04-29", "2024-05-01", 10,
        ["Beverages", "Snacks & confectionery"], 0, "Labour Day")
    add("Madaraka Weekend", "Seasonal percent-off", "2024-05-30", "2024-06-02", 10,
        ["Beverages", "Snacks & confectionery"], 0, "Madaraka Day")
    add("Fresh Produce Week", "Category promotion", "2024-07-08", "2024-07-14", 15, ["Fresh produce"], 0, "")
    add("Back-to-School Home Care", "Seasonal percent-off", "2024-08-26", "2024-09-08", 10,
        ["Toiletries & personal care", "Household cleaning"], 0, "School term 3 opening")
    add("Mashujaa Weekend", "Seasonal percent-off", "2024-10-18", "2024-10-21", 10,
        ["Beverages", "Snacks & confectionery"], 0, "Mashujaa Day")
    add("Black Friday", "Storewide percent-off", "2024-11-25", "2024-12-01", 20, "ALL", 0, "Black Friday")
    add("Christmas Feast", "Seasonal percent-off", "2024-12-14", "2024-12-24", 12,
        ["Cooking oil & fats", "Sugar & sweeteners", "Dairy & eggs", "Beverages", "Snacks & confectionery"], 0,
        "Christmas")
    add("Festive Season Treats", "Seasonal percent-off", "2024-12-26", "2024-12-31", 10,
        ["Beverages", "Snacks & confectionery"], 0, "Boxing Day / New Year")
    for m in range(1, 13):
        last = (date(YEAR, m, 28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        add(f"Payday Saver {date(YEAR, m, 1):%b}", "Loyalty payday", f"{YEAR}-{m:02d}-25",
            last.isoformat(), 5, "ALL", 1, "Month-end payday")
    for i, p in enumerate(P, 1):
        p["promo_id"] = f"PR{i:02d}"
    return P


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def poisson(rng, lam):
    """Knuth's method; fine for the small lambdas used here."""
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def cum(weights):
    out, s = [], 0.0
    for w in weights:
        s += w
        out.append(s)
    return out


def division_index(rows):
    """Chain the published month-on-month % changes into a price index with Jan 2024 = 1.0."""
    idx = {}
    divisions = sorted({r["coicop_division"] for r in rows})
    for div in divisions:
        mom = {int(r["month"][-2:]): float(r["mom_change_pct"]) for r in rows if r["coicop_division"] == div}
        level, levels = 100.0, {}
        for m in range(1, 13):
            level *= 1 + mom[m] / 100.0
            levels[m] = level
        idx[div] = {m: levels[m] / levels[1] for m in levels}
    return idx


# ----------------------------------------------------------------------------
# build tables
# ----------------------------------------------------------------------------
def build_stores(rng, county_code):
    rows, n = [], 0
    for county, stores, catchment in STORE_PLAN:
        for fmt, loc in stores:
            n += 1
            lo, hi = FORMAT_AREA_SQM[fmt]
            level = FORMAT_PRICE_FACTOR[fmt] * (1.02 if county in ("Nairobi", "Mombasa") else 1.0)
            rows.append(dict(
                store_id=f"S{n:02d}", store_name=f"Soko Fresh {loc}", county_code=county_code[county],
                county=county, format=fmt, catchment_type=catchment, floor_area_sqm=rng.randrange(lo, hi, 50),
                opening_date=(date(2012, 1, 1) + timedelta(days=rng.randrange(0, 4000))).isoformat(),
                price_level_index=round(level, 3)))
    return rows


def build_products(rng):
    brand_mult = {b: (0.85 if b == OWN_LABEL else round(rng.uniform(0.92, 1.30), 3)) for b in BRANDS}
    rows, n = [], 0
    for cat, spec in CATEGORIES.items():
        brands = rng.sample([b for b in BRANDS if b != OWN_LABEL], spec["nbrand"] - 1) + [OWN_LABEL]
        combos = [(it, b) for it in spec["items"] for b in brands]
        rng.shuffle(combos)
        for (item, size, price, src), brand in combos[: spec["n"]]:
            n += 1
            list_price = max(5, round(price * brand_mult[brand] * rng.uniform(0.97, 1.03)))
            cost = round(list_price * (1 - spec["margin"]) * rng.uniform(0.97, 1.03), 2)
            rows.append(dict(
                product_id=f"P{n:04d}", sku=f"SKU{100000 + n}", product_name=f"{brand} {item} {size}",
                category=cat, brand=brand, unit_size=size, base_price_kes=list_price, base_cost_kes=cost,
                cpi_division=spec["div"], price_anchor_source=src))
    return rows


def build_customers(rng, store_counties, county_code, population):
    w = [population[c] for c in store_counties]
    rows = []
    for i in range(1, ARGS.customers + 1):
        county = rng.choices(store_counties, weights=w)[0]
        loyal = 1 if rng.random() < LOYALTY_RATE else 0
        rows.append(dict(
            customer_id=f"C{i:05d}", home_county_code=county_code[county], home_county=county,
            gender=rng.choices(["F", "M", "Unspecified"], weights=[55, 42, 3])[0],
            age_band=rng.choices(["18-24", "25-34", "35-44", "45-54", "55+"], weights=[18, 32, 24, 15, 11])[0],
            loyalty_member=loyal,
            registration_date=(date(2018, 1, 1) + timedelta(days=rng.randrange(0, 2190))).isoformat()))
    return rows


def day_weights(days, holidays):
    hol = {h["date"] for h in holidays}
    out = []
    for d in days:
        w = {0: 0.95, 1: 0.90, 2: 0.95, 3: 1.00, 4: 1.15, 5: 1.35, 6: 1.15}[d.weekday()]
        if d.day >= 25 or d.day <= 2:
            w *= 1.20                         # payday / month-start shopping
        if d.month == 12:
            w *= 1.40 if d.day >= 14 else 1.15
        if d.isoformat() in hol or (d + timedelta(days=1)).isoformat() in hol:
            w *= 1.15
        if d.month == 11 and 25 <= d.day <= 30:
            w *= 1.35                         # Black Friday week
        out.append(w)
    return out


def main():
    rng = random.Random(ARGS.seed)

    # ---- real inputs
    cpi_overall = {int(r["month"][-2:]): r for r in read_csv(EXT / "cpi_monthly_2024.csv")}
    div_rows = read_csv(EXT / "cpi_by_division_2024.csv")
    idx = division_index(div_rows)
    pop_rows = read_csv(EXT / "county_population_2019.csv")
    county_code = {r["county"]: int(r["county_code"]) for r in pop_rows}
    population = {r["county"]: int(r["population_total"]) for r in pop_rows}
    usage = {r["county"]: r for r in read_csv(EXT / "payment_mix_by_county.csv")}
    holidays = read_csv(EXT / "public_holidays_2024.csv")
    yoy = {m: float(cpi_overall[m]["yoy_inflation_pct"]) for m in cpi_overall}
    mean_yoy = sum(yoy.values()) / len(yoy)

    # ---- simulated dimensions
    stores = build_stores(rng, county_code)
    products = build_products(rng)
    store_counties = sorted({s["county"] for s in stores})
    customers = build_customers(rng, store_counties, county_code, population)
    promos = promo_plan()

    # promo lookup by date
    days = [date(YEAR, 1, 1) + timedelta(days=i) for i in range((date(YEAR, 12, 31) - date(YEAR, 1, 1)).days + 1)]
    active = {d: [] for d in days}
    for p in promos:
        s, e = date.fromisoformat(p["start_date"]), date.fromisoformat(p["end_date"])
        cats = None if p["categories"] == "ALL" else set(p["categories"])
        for d in days:
            if s <= d <= e:
                active[d].append((p["promo_id"], p["discount_pct"] / 100.0, cats, p["loyalty_only"]))
    for p in promos:  # flatten the list for CSV
        if p["categories"] != "ALL":
            p["categories"] = ";".join(p["categories"])

    # product lookup
    by_cat = {}
    for p in products:
        by_cat.setdefault(p["category"], []).append(p)
    cat_names = list(CATEGORIES)
    cat_cum = cum([CATEGORIES[c]["share"] for c in cat_names])
    prod_cum = {}
    for c, plist in by_cat.items():
        ranks = list(range(1, len(plist) + 1))
        rng.shuffle(ranks)
        by_cat[c] = plist
        prod_cum[c] = cum([1.0 / (r ** 0.8) for r in ranks])

    # store traffic and payment probabilities per (store, month)
    stores_by_id = {s["store_id"]: s for s in stores}
    traffic = {s["store_id"]: FORMAT_TRAFFIC_WEIGHT[s["format"]] * (population[s["county"]] / 1e6) ** 0.4
               for s in stores}
    store_ids = list(traffic)
    store_cum = cum([traffic[i] for i in store_ids])
    stores_in_county = {}
    for s in stores:
        stores_in_county.setdefault(s["county"], []).append(s["store_id"])
    county_store_cum = {c: cum([traffic[i] for i in ids]) for c, ids in stores_in_county.items()}

    def pay_probs(store, month):
        u = usage[store["county"]]
        d = float(u["mobile_money_usage_pct"]) / 100.0
        cash = CASH_BASE - CASH_DIGITAL_SLOPE * d + CATCHMENT_CASH_ADJ[store["catchment_type"]]
        cash += CASH_INFLATION_SENSITIVITY * (yoy[month] - mean_yoy) / 100.0
        cash = min(max(cash, 0.12), 0.70)
        card = (CARD_BASE + CARD_BANK_SLOPE * float(u["bank_usage_excl_mobile_bank_pct"]) / 100.0) \
            * FORMAT_CARD_MULT[store["format"]]
        card = min(max(card, 0.01), 0.30)
        mobile = max(1.0 - cash - card, 0.0)
        return [cash, mobile * MPESA_SHARE_OF_MOBILE, mobile * (1 - MPESA_SHARE_OF_MOBILE), card]
    PAY_METHODS = ["Cash", "M-Pesa", "Airtel Money", "Card"]
    pay_table = {(s["store_id"], m): pay_probs(s, m) for s in stores for m in range(1, 13)}

    # customers: traffic weights; loyalty members shop more
    cust_w = [rng.lognormvariate(0, 0.9) * (2.0 if c["loyalty_member"] else 1.0) for c in customers]
    cust_cum = cum(cust_w)
    loyal_of = {c["customer_id"]: c["loyalty_member"] for c in customers}
    county_of_cust = {c["customer_id"]: c["home_county"] for c in customers}

    dcum = cum(day_weights(days, holidays))
    hours = list(HOUR_WEIGHTS)
    hcum = cum([HOUR_WEIGHTS[h] for h in hours])

    # ---- transactions and lines
    txns, lines = [], []
    line_no = 0
    for t in range(1, ARGS.transactions + 1):
        d = rng.choices(days, cum_weights=dcum)[0]
        linked = rng.random() < SHARE_LINKED_TXNS
        if linked:
            cust = customers[rng.choices(range(len(customers)), cum_weights=cust_cum)[0]]
            cid = cust["customer_id"]
            county = cust["home_county"]
            sid = rng.choices(stores_in_county[county], cum_weights=county_store_cum[county])[0]
            loyal = cust["loyalty_member"]
        else:
            cid, loyal = "", 0
            sid = rng.choices(store_ids, cum_weights=store_cum)[0]
        store = stores_by_id[sid]
        month = d.month
        method = rng.choices(PAY_METHODS, weights=pay_table[(sid, month)])[0]
        hour = rng.choices(hours, cum_weights=hcum)[0]
        ts = datetime(d.year, d.month, d.day, hour, rng.randrange(60), rng.randrange(60))

        n_lines = min(1 + poisson(rng, FORMAT_LINES_LAMBDA[store["format"]]), 15)
        chosen, gross, disc_total = set(), 0.0, 0.0
        for _ in range(n_lines):
            cat = cat_names[rng.choices(range(len(cat_names)), cum_weights=cat_cum)[0]]
            plist = by_cat[cat]
            prod = plist[rng.choices(range(len(plist)), cum_weights=prod_cum[cat])[0]]
            if prod["product_id"] in chosen:
                continue
            chosen.add(prod["product_id"])
            spec = CATEGORIES[cat]
            mult = idx[spec["div"]][month]
            price = max(1, round(float(prod["base_price_kes"]) * mult * float(store["price_level_index"])))
            cost = round(float(prod["base_cost_kes"]) * mult, 2)
            best_pct, best_id = 0.0, ""
            for pid, pct, cats, loyalty_only in active[d]:
                if (cats is None or cat in cats) and (not loyalty_only or loyal) and pct > best_pct:
                    best_pct, best_id = pct, pid
            demand = (mult ** spec["elast"]) * (1 + PROMO_LIFT * best_pct)
            qty = min(1 + poisson(rng, UNITS_LAMBDA * demand), 12)
            line_gross = price * qty
            disc = round(line_gross * best_pct, 2)
            line_no += 1
            lines.append(dict(
                line_id=line_no, transaction_id=f"T{t:07d}", product_id=prod["product_id"], quantity=qty,
                unit_price_kes=price, unit_cost_kes=cost, discount_pct=round(best_pct * 100, 1),
                discount_kes=disc, promo_id=best_id, line_net_kes=round(line_gross - disc, 2)))
            gross += line_gross
            disc_total += disc
        txns.append(dict(
            transaction_id=f"T{t:07d}", store_id=sid, customer_id=cid, transaction_date=d.isoformat(),
            transaction_time=ts.strftime("%H:%M:%S"), payment_method=method, n_lines=len(chosen),
            gross_kes=round(gross, 2), discount_kes=round(disc_total, 2), net_kes=round(gross - disc_total, 2)))

    # ---- write
    OUT.mkdir(parents=True, exist_ok=True)
    tables = {
        "stores": (["store_id", "store_name", "county_code", "county", "format", "catchment_type",
                    "floor_area_sqm", "opening_date", "price_level_index"], stores),
        "products": (["product_id", "sku", "product_name", "category", "brand", "unit_size", "base_price_kes",
                      "base_cost_kes", "cpi_division", "price_anchor_source"], products),
        "customers": (["customer_id", "home_county_code", "home_county", "gender", "age_band", "loyalty_member",
                       "registration_date"], customers),
        "promotions": (["promo_id", "promo_name", "promo_type", "start_date", "end_date", "discount_pct",
                        "categories", "loyalty_only", "anchor_event"], promos),
        "transactions": (["transaction_id", "store_id", "customer_id", "transaction_date", "transaction_time",
                          "payment_method", "n_lines", "gross_kes", "discount_kes", "net_kes"], txns),
        "transaction_lines": (["line_id", "transaction_id", "product_id", "quantity", "unit_price_kes",
                               "unit_cost_kes", "discount_pct", "discount_kes", "promo_id", "line_net_kes"], lines),
    }
    log = {"seed": ARGS.seed, "year": YEAR, "n_transactions_requested": ARGS.transactions,
           "n_customers_requested": ARGS.customers, "synthetic": True, "files": {}}
    for name, (cols, rows) in tables.items():
        path = OUT / f"{name}.csv"
        write_csv(path, cols, rows)
        log["files"][f"{name}.csv"] = {"rows": len(rows), "bytes": path.stat().st_size, "sha256": sha256(path)}
        print(f"{name:18s} {len(rows):>9,} rows  {path.stat().st_size / 1e6:6.2f} MB")
    with open(OUT / "generation_log.json", "w") as f:
        json.dump(log, f, indent=2)
    print("Done. Log written to", OUT / "generation_log.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate the synthetic retail tables.")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--transactions", type=int, default=60000)
    ap.add_argument("--customers", type=int, default=8000)
    ARGS = ap.parse_args()
    sys.exit(main())
