"""
06_returns.py: from estimated revenue to a 2027 return, for three ways of
running the same unit, then a portfolio and a range.

  A. Full-time short stays (pays the vacancy taxes: EHT 3% + SVT 1%)
  B. Hybrid: short stays May-Oct, 30+ night stays Nov-Apr (exempt from both)
  C. Plain long-term rental at CMHC rents (exempt; the fallback / hurdle)

Return metric: net operating income / all-in purchase cost, no borrowing.

FIRST PASS. Every constant in ASSUMPTIONS below marked "assumption" is a
placeholder that still needs a public source before it goes on a slide.

Run:  python src/06_returns.py      (after 05_revenue.py)
Out:  outputs/06_*.csv, outputs/06_three_models.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config
from common import record_key_numbers

SCRIPT = "06_returns.py"
SEED = 42
BUDGET = 10_000_000

# ---------------------------------------------------------------- assumptions
VACANCY_TAX = 0.03 + 0.01        # EHT 3% (City of Vancouver) + SVT 1% (gov.bc.ca, Canadian owner, 2026-27)
PROPERTY_TAX = 0.00336394        # Vancouver 2026 residential rate (council report, Apr 28 2026)
AIRBNB_FEE = 0.155               # host-only fee, share of short-stay revenue
MGMT_STR = 0.20                  # assumption: full-service manager incl. turnover, share of short-stay revenue
MGMT_LONG = 0.08                 # assumption: manager fee on 30+ night / long-term rent
FURNISH_LEGAL = 25_000           # assumption: furnishing + legal per unit
LICENCES = 1_108 + 450           # City STR licence + provincial registration (to confirm on vancouver.ca)
# Fixed yearly costs per unit by property type (assumptions): strata fees, insurance, utilities+internet, upkeep
FIXED = {"apartment": {"strata": 5_400, "insurance": 1_200, "utilities": 2_400, "upkeep": 1_500},
         "detached":  {"strata": 0,     "insurance": 3_000, "utilities": 4_800, "upkeep": 6_000}}
PEAK_MONTHS = [5, 6, 7, 8, 9, 10]   # hybrid: short stays in these months
WINTER_FILL = 0.85               # assumption: share of the 6 off-season months actually let

WEST = ["Downtown", "West End", "Kitsilano", "Fairview", "West Point Grey", "Dunbar Southlands",
        "Arbutus Ridge", "Kerrisdale", "Shaughnessy", "South Cambie", "Oakridge", "Marpole"]
APARTMENT_TYPES = ["Entire rental unit", "Entire condo", "Entire loft", "Entire serviced apartment"]
HOUSE_TYPES = ["Entire home", "Entire townhouse", "Entire villa", "Entire bungalow", "Entire cottage"]
# CMHC zones used for each side of the city (simple average of zone average rents)
CMHC_ZONES = {"West": ["West End/Stanley Park", "English Bay", "Downtown", "South Granville/Oak", "Kitsilano/Point Grey"],
              "East": ["Mount Pleasant/Renfrew Heights", "East Hastings", "Southeast Vancouver"]}


def ptt(price):
    """BC Property Transfer Tax: 1% to $200k, 2% to $2M, 3% above."""
    return 0.01 * min(price, 200_000) + 0.02 * max(min(price, 2_000_000) - 200_000, 0) + 0.03 * max(price - 2_000_000, 0)


# ---------------------------------------------------------------- data
rev = pd.read_parquet(config.PROCESSED / "listings_revenue.parquet")
scope = pd.read_parquet(config.PROCESSED / "listings_scope.parquet")[["id", "property_type"]]
d = rev.merge(scope, on="id").dropna(subset=["revenue_base", "bedrooms"])
d["side"] = np.where(d["neighbourhood_cleansed"].isin(WEST), "West", "East")
d["ptype"] = np.select([d["property_type"].isin(APARTMENT_TYPES), d["property_type"].isin(HOUSE_TYPES)],
                       ["apartment", "detached"], default="other")
d["beds"] = d["bedrooms"].clip(upper=3).astype(int)
print("Property-type mapping:\n", d["ptype"].value_counts().to_string())
# 'other' is mostly guest suites / guesthouses: part of someone's house, not a unit DDD can buy alone.
seg = d[((d["ptype"] == "apartment") & d["beds"].isin([1, 2])) | ((d["ptype"] == "detached") & (d["beds"] == 3))].copy()

# Seasonality: share of a year's reviews that fall in the peak months (in-scope listings, last 2 full years)
reviews = pd.read_parquet(config.PROCESSED / "reviews_clean.parquet")
rv = reviews[reviews["listing_id"].isin(rev["id"]) & reviews["date"].between("2024-06-01", "2026-05-31")]
peak_share = float(rv["date"].dt.month.isin(PEAK_MONTHS).mean())
print(f"Share of reviews in May-Oct: {peak_share:.3f}")

# Ramp-up: DDD's units are new listings in 2027. For in-scope listings whose first review was
# 24-36 months before the scrape, compare reviews in their first 12 months with months 13-24.
first = reviews.groupby("listing_id")["date"].min()
cohort = first[first.between("2023-06-15", "2024-06-15") & first.index.isin(rev["id"])]
r2 = reviews[reviews["listing_id"].isin(cohort.index)].merge(cohort.rename("first"), left_on="listing_id", right_index=True)
age = (r2["date"] - r2["first"]).dt.days
y1 = r2[age < 365].groupby("listing_id").size().reindex(cohort.index, fill_value=0)
y2 = r2[(age >= 365) & (age < 730)].groupby("listing_id").size().reindex(cohort.index, fill_value=0)
RAMP_2027 = float(y1.sum() / y2.sum())
print(f"Ramp-up cohort: {len(cohort)} listings; year-1 reviews / year-2 reviews = {RAMP_2027:.2f} "
      f"(survivors only: listings that closed are not in the snapshot)")
RAMP_2027 = min(RAMP_2027, 1.0)

# Winter monthly rate: Airbnb listings with a 30+ night minimum, quoted for a 30+ night stay
clean = pd.read_parquet(config.PROCESSED / "listings_clean.parquet")
mid = clean[clean["is_entire_home"] & (clean["minimum_nights"] >= 30) & clean["price"].notna()
            & (clean["price_quote_nights"] >= 30) & clean["property_type"].isin(APARTMENT_TYPES + HOUSE_TYPES)].copy()
mid["side"] = np.where(mid["neighbourhood_cleansed"].isin(WEST), "West", "East")
mid["ptype"] = np.where(mid["property_type"].isin(APARTMENT_TYPES), "apartment", "detached")
mid["beds"] = mid["bedrooms"].clip(upper=3)
mid["monthly"] = mid["price"] * 30
mid_active_share = float((mid["number_of_reviews_ltm"] > 0).mean())

# CMHC long-term rents (Oct 2025)
def cmhc(beds):
    f = config.EXTERNAL / f"cmhc_rent_{beds}bed_oct2025.csv"
    t = pd.read_csv(f, skiprows=2, encoding="latin-1", index_col=0)
    return pd.to_numeric(t["Average Rent ($)"].astype(str).str.replace(",", ""), errors="coerce")

gvr = pd.read_csv(config.EXTERNAL / "gvr_benchmark_prices.csv").set_index(["area", "property_type"])["benchmark_price"]

# ---------------------------------------------------------------- unit economics per segment
rows = []
for (side, ptype, beds), g in seg.groupby(["side", "ptype", "beds"]):
    price = float(gvr[(f"Vancouver {side}", ptype)])
    allin = price + ptt(price) + FURNISH_LEGAL
    fixed = sum(FIXED[ptype].values()) + PROPERTY_TAX * price
    m = mid[(mid["side"] == side) & (mid["ptype"] == ptype) & (mid["beds"] == beds)]["monthly"]
    ltr = float(cmhc(beds)[CMHC_ZONES[side]].mean())
    for label, q in [("median", .5), ("p75", .75)]:
        str_rev = float(g["revenue_base"].quantile(q)) * RAMP_2027
        a = str_rev * (1 - AIRBNB_FEE - MGMT_STR) - fixed - LICENCES
        a_tax = a - VACANCY_TAX * price
        winter = 6 * WINTER_FILL * float(m.median()) if len(m) >= 10 else np.nan
        b = (float(g["revenue_rate_high"].quantile(q)) * RAMP_2027 * peak_share * (1 - AIRBNB_FEE - MGMT_STR)
             + winter * (1 - MGMT_LONG) - fixed - LICENCES)
        c = 12 * ltr * (1 - MGMT_LONG) * 0.97 - (fixed - FIXED[ptype]["utilities"])   # tenant pays utilities; 3% vacancy
        rows.append(dict(side=side, ptype=ptype, beds=beds, comparable=label, n_str=len(g), n_midterm=len(m),
                         price=price, all_in=round(allin), str_revenue=round(str_rev),
                         winter_monthly=round(float(m.median())) if len(m) >= 10 else np.nan, cmhc_rent=round(ltr),
                         yield_A_no_tax=100 * a / allin, yield_A_with_tax=100 * a_tax / allin,
                         yield_B_hybrid=100 * b / allin, yield_C_long_term=100 * c / allin,
                         revenue_per_1000_invested=1000 * str_rev / allin))
t = pd.DataFrame(rows).round(1)
t.to_csv(config.OUTPUTS / "06_three_models_by_segment.csv", index=False)
print(t.to_string(index=False))

# ---------------------------------------------------------------- portfolio + range (best segment under each model)
rng = np.random.default_rng(SEED)
port = []
for (side, ptype, beds), g in seg.groupby(["side", "ptype", "beds"]):
    price = float(gvr[(f"Vancouver {side}", ptype)])
    allin = price + ptt(price) + FURNISH_LEGAL
    n = int((BUDGET * 0.95) // allin)            # 5% held back as a reserve (assumption)
    fixed = sum(FIXED[ptype].values()) + PROPERTY_TAX * price + LICENCES
    draws = rng.choice(g["revenue_base"].to_numpy(), size=(10_000, n), replace=True) * RAMP_2027
    noi = (draws * (1 - AIRBNB_FEE - MGMT_STR) - fixed).sum(axis=1)
    y = 100 * noi / BUDGET
    m = mid[(mid["side"] == side) & (mid["ptype"] == ptype) & (mid["beds"] == beds)]["monthly"].to_numpy()
    if len(m) >= 10:
        hs = rng.choice(g["revenue_rate_high"].to_numpy(), size=(10_000, n)) * RAMP_2027 * peak_share * (1 - AIRBNB_FEE - MGMT_STR)
        hw = rng.choice(m, size=(10_000, n)) * 6 * WINTER_FILL * (1 - MGMT_LONG)
        yb = 100 * (hs + hw - fixed).sum(axis=1) / BUDGET
    else:
        yb = np.full(10_000, np.nan)
    port.append(dict(side=side, ptype=ptype, beds=beds, units=n, invested=round(n * allin),
                     hybrid_p10=np.percentile(yb, 10), hybrid_p50=np.percentile(yb, 50), hybrid_p90=np.percentile(yb, 90),
                     hybrid_noi_p50=round(np.percentile(yb, 50) * BUDGET / 100),
                     A_no_tax_p10=np.percentile(y, 10), A_no_tax_p50=np.percentile(y, 50), A_no_tax_p90=np.percentile(y, 90),
                     vacancy_tax_pct_of_budget=100 * VACANCY_TAX * price * n / BUDGET))
p = pd.DataFrame(port).round(2)
p.to_csv(config.OUTPUTS / "06_portfolio_range.csv", index=False)
print("\nPortfolio if all $10M went to one segment (full-time short stays, before vacancy taxes; % of $10M)\n", p.to_string(index=False))

# ---------------------------------------------------------------- chart: three models, median comparable
c = t[t["comparable"] == "median"].copy()
c["label"] = c["side"] + " " + c["ptype"] + " " + c["beds"].astype(str) + "-bed"
fig, ax = plt.subplots(figsize=(9, 4.8))
x = np.arange(len(c)); w = 0.27
for i, (col, name, colour) in enumerate([("yield_A_with_tax", "Full-time short stays (pays vacancy taxes)", "#c0504d"),
                                         ("yield_B_hybrid", "Hybrid (short stays May-Oct, monthly Nov-Apr)", "#1f5fa8"),
                                         ("yield_C_long_term", "Long-term rental (CMHC rents)", "#7f7f7f")]):
    ax.bar(x + (i - 1) * w, c[col], w, label=name, color=colour)
ax.axhline(0, color="black", lw=.8)
ax.set_xticks(x, c["label"], rotation=20, ha="right")
ax.set_ylabel("Net yield on all-in cost, % per year")
ax.set_title("Same unit, three ways to run it (median comparable listing; first-pass cost assumptions)", loc="left", fontsize=10)
ax.legend(fontsize=8, frameon=False)
ax.spines[["top", "right"]].set_visible(False)
fig.text(0.01, 0.01, config.CREDIT_LINE_WITH_MARCH + " CMHC Rental Market Survey, Oct 2025. GVR benchmark prices, Oct 2026.",
         fontsize=7, color="#555555")
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(config.OUTPUTS / "06_three_models.png", dpi=200)

record_key_numbers([
    ("peak_review_share", round(100 * peak_share, 1), "% of reviews", "May-Oct share, in-scope listings, Jun 2024 - May 2026"),
    ("ramp_up_factor", round(RAMP_2027, 2), "ratio", "year-1 / year-2 reviews, listings first reviewed Jun 2023 - Jun 2024, capped at 1"),
    ("midterm_listings_used", len(mid), "listings", "entire homes, 30+ night minimum, 30+ night quote"),
    ("midterm_reviewed_share", round(100 * mid_active_share, 1), "% of those", "at least 1 review in last 12 months"),
], SCRIPT)
