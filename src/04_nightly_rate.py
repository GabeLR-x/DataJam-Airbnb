"""
04_nightly_rate.py: one nightly rate per in-scope listing, built from price
quotes in two seasons (March and June 2026) instead of June alone.

Why: the June price is a single quote taken in peak season during the World
Cup (decision log #5). Averaging it with the SAME listing's March price (low
season, before the event) pulls the rate toward a normal year. It is still two
dates, not twelve months, and June keeps some event premium.

A three-snapshot version (with September 2026) was tested and dropped: it
moved the median rate by about 1% (decision log #5; git commit 9f2b819).

No revenue is modelled here.

Run:  python src/04_nightly_rate.py      (after 03_scope_and_price.py)
Out:  data/processed/listings_rate.parquet
      outputs/04_rate_coverage.csv, 04_rate_medians.csv, 04_rate_ratio.csv
"""
import pandas as pd

import config
from common import record_key_numbers

SCRIPT = "04_nightly_rate.py"
MAX_N = config.MID_TERM_MIN_NIGHTS  # quotes for 30+ nights are monthly rates, not nightly


def load_snapshot_prices(folder, tag):
    """Read id + price quote from the March snapshot and return usable prices.

    Privacy: only id, price and the two quote dates are read, so host names,
    URLs and licence text from that file never enter memory.
    Usable = price parsed AND the quoted stay is under 30 nights.
    """
    df = pd.read_csv(folder / "listings.csv.gz", dtype=str,
                     usecols=["id", "price", "price_quote_checkin_date", "price_quote_checkout_date"])
    price = pd.to_numeric(df["price"].str.replace(r"[$,\s]", "", regex=True), errors="coerce")
    failed = int((df["price"].notna() & price.isna()).sum())
    nights = (pd.to_datetime(df["price_quote_checkout_date"], format=config.DATE_FORMAT, errors="coerce")
              - pd.to_datetime(df["price_quote_checkin_date"], format=config.DATE_FORMAT, errors="coerce")).dt.days
    usable = price.notna() & (nights < MAX_N)
    print(f"{tag}: {len(df):,} listings | priced {int(price.notna().sum()):,} | parse failures {failed} "
          f"| usable (quote < {MAX_N} nights) {int(usable.sum()):,}")
    return df.loc[usable, ["id"]].assign(**{f"price_{tag}": price[usable]})


# ==========================================================================
# 1. March and June prices for in-scope listings
# ==========================================================================
scope = pd.read_parquet(config.PROCESSED / "listings_scope.parquet")
print(f"In-scope listings (from 03): {len(scope):,}")
r = scope[["id", "neighbourhood_cleansed"]].copy()
# June: same "usable" rule as March.
r["price_jun"] = scope["price"].where(scope["price_quote_nights"] < MAX_N)
print(f"jun: usable (quote < {MAX_N} nights) {int(r['price_jun'].notna().sum()):,}")
r = r.merge(load_snapshot_prices(config.RAW_PRE_WORLDCUP, "mar"), on="id", how="left")
assert len(r) == len(scope), "The merge duplicated listings."

# ==========================================================================
# 2. Coverage: how many listings have a usable price in both snapshots
# ==========================================================================
r["coverage"] = "no usable June price"
r.loc[r["price_jun"].notna(), "coverage"] = "June only"
r.loc[r["price_jun"].notna() & r["price_mar"].notna(), "coverage"] = "March + June"
coverage = r["coverage"].value_counts().rename("listings").to_frame()
coverage["% of scope"] = (100 * coverage["listings"] / len(r)).round(1)
coverage.to_csv(config.OUTPUTS / "04_rate_coverage.csv")
print("\nCoverage of in-scope listings\n", coverage.to_string())

# ==========================================================================
# 3. Listings with both prices: rate = mean of March and June
# ==========================================================================
# Each season counts equally. March is low season and June is peak, so the
# mean sits between them; it is not weighted by how long each season lasts.
both = r[r["coverage"] == "March + June"].copy()
both["rate_2"] = both[["price_mar", "price_jun"]].mean(axis=1)
both["ratio"] = both["rate_2"] / both["price_jun"]          # March+June average / June
both["ratio_mar"] = both["price_mar"] / both["price_jun"]   # March / June, for the low scenario
both["core"] = both["neighbourhood_cleansed"].isin(config.WORLD_CUP_CORE_AREAS)


def medians(d):
    """Medians across listings: robust to the few very expensive homes."""
    return pd.Series({"listings": len(d), "median_mar": d["price_mar"].median(),
                      "median_jun": d["price_jun"].median(),
                      "median_mar_jun_avg": round(d["rate_2"].median(), 2),
                      "median_ratio_avg_to_jun": round(d["ratio"].median(), 3)})


by_area = both.groupby("neighbourhood_cleansed").apply(medians).sort_values("listings", ascending=False)
by_area["small_n_flag"] = (by_area["listings"] < config.SMALL_N_THRESHOLD).map({True: "SMALL", False: ""})
overall = medians(both).to_frame("ALL AREAS").T
med = pd.concat([overall, by_area]).fillna({"small_n_flag": ""}).astype({"listings": int})
med.index.name = "neighbourhood"
med.to_csv(config.OUTPUTS / "04_rate_medians.csv")
print("\nMedian price by snapshot, listings priced in both\n", med.to_string())

# Ratio = median of each listing's own (average / June), split by area to test
# whether one citywide ratio is fair to the stadium area.
parts = {"All areas": both, "Downtown + West End": both[both["core"]], "All other areas": both[~both["core"]]}
ratio_tab = pd.DataFrame({g: medians(d) for g, d in parts.items()}).T
ratio_tab["p25_ratio"] = [d["ratio"].quantile(.25).round(3) for d in parts.values()]
ratio_tab["p75_ratio"] = [d["ratio"].quantile(.75).round(3) for d in parts.values()]
ratio_tab = ratio_tab.astype({"listings": int}).rename_axis("group")
ratio_tab.to_csv(config.OUTPUTS / "04_rate_ratio.csv")
print("\nRatio: March+June average / June price\n", ratio_tab.to_string())
RATIO = float(both["ratio"].median())          # applied to June-only listings
RATIO_MAR = float(both["ratio_mar"].median())  # March level as a share of June

# ==========================================================================
# 4. June-only listings: June price x overall ratio
# ==========================================================================
# They have no March price of their own, so we assume they sit as far below
# June as the typical listing with both prices does, and flag them.
r["rate_base"] = r[["price_mar", "price_jun"]].mean(axis=1).where(r["coverage"] == "March + June")
adjust = r["coverage"] == "June only"
r.loc[adjust, "rate_base"] = r.loc[adjust, "price_jun"] * RATIO
r["rate_adjusted"] = adjust
# Scenarios from decision log #5. Low = March level: the listing's own March
# price if it has one, otherwise June x the median March/June ratio.
r["rate_low"] = r["price_mar"].where(r["price_jun"].notna()).fillna(r["price_jun"] * RATIO_MAR)
r["rate_high"] = r["price_jun"]                      # June as it is
n_rate = int(r["rate_base"].notna().sum())
print(f"\nRate from own March + June prices: {len(both):,} | June x {RATIO:.3f} (rate_adjusted): "
      f"{int(adjust.sum()):,} | no rate (no usable June price): {len(r) - n_rate}")
scen = r[["rate_low", "rate_base", "rate_high"]].median().round(2)
print("Median nightly rate, all in-scope listings with a rate:", scen.to_dict())

# ==========================================================================
# 5. Save
# ==========================================================================
r.to_parquet(config.PROCESSED / "listings_rate.parquet", index=False)
note2 = "in-scope listings with a usable price (quote < 30 nights) in both Mar and Jun 2026"
o, rt = overall.iloc[0], ratio_tab
record_key_numbers([
    ("rate_listings_mar_jun", int(o["listings"]), "listings", note2),
    ("rate_listings_mar_jun_share", coverage.loc["March + June", "% of scope"], "% of in-scope listings", note2),
    ("rate_listings_adjusted", int(adjust.sum()), "listings", "June only: June price x overall ratio"),
    ("rate_listings_no_rate", len(r) - n_rate, "listings", "in scope but no usable June price"),
    ("rate_median_mar", o["median_mar"], "CAD/night", note2),
    ("rate_median_jun", o["median_jun"], "CAD/night", note2 + "; World Cup period"),
    ("rate_median_mar_jun_avg", o["median_mar_jun_avg"], "CAD/night", note2),
    ("rate_ratio_avg_to_jun", round(RATIO, 3), "ratio", "median of per-listing (Mar+Jun avg / June)"),
    ("rate_ratio_avg_to_jun_core", rt.loc["Downtown + West End", "median_ratio_avg_to_jun"], "ratio", "Downtown + West End"),
    ("rate_ratio_avg_to_jun_other", rt.loc["All other areas", "median_ratio_avg_to_jun"], "ratio", "all other areas"),
    ("rate_ratio_mar_to_jun", round(RATIO_MAR, 3), "ratio", "median of per-listing (March / June); low scenario"),
    ("rate_base_median", scen["rate_base"], "CAD/night", "base case, all in-scope listings with a rate"),
    ("rate_low_median", scen["rate_low"], "CAD/night", "low scenario: March level"),
    ("rate_high_median", scen["rate_high"], "CAD/night", "high scenario: June as it is"),
], SCRIPT)
print("\n" + config.CREDIT_LINE_WITH_MARCH)
