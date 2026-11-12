"""
04_nightly_rate.py: one nightly rate per in-scope listing, built from price
quotes in three seasons (March, June, September 2026) instead of June alone.

Why: the June price is a single quote taken in peak season during the World
Cup (decision log #5). Averaging three snapshots of the SAME listing spreads
the rate over low, peak and shoulder season. It is still three dates, not
twelve months, and June keeps some event premium, so it leans slightly high.

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
    """Read id + price quote from another snapshot and return usable prices.

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
# 1. Prices from the three snapshots, for in-scope listings
# ==========================================================================
scope = pd.read_parquet(config.PROCESSED / "listings_scope.parquet")
print(f"In-scope listings (from 03): {len(scope):,}")
r = scope[["id", "neighbourhood_cleansed"]].copy()
# June: same "usable" rule as the other two snapshots.
r["price_jun"] = scope["price"].where(scope["price_quote_nights"] < MAX_N)
print(f"jun: usable (quote < {MAX_N} nights) {int(r['price_jun'].notna().sum()):,}")
r = r.merge(load_snapshot_prices(config.RAW_PRE_WORLDCUP, "mar"), on="id", how="left")
r = r.merge(load_snapshot_prices(config.RAW_VALIDATION, "sep"), on="id", how="left")
assert len(r) == len(scope), "A merge duplicated listings."

# ==========================================================================
# 2. Coverage: how many listings have a usable price in 3, 2, 1 snapshots
# ==========================================================================
has = r[["price_mar", "price_jun", "price_sep"]].notna()
r["coverage"] = "no usable June price"
r.loc[has["price_jun"], "coverage"] = "June only"
r.loc[has["price_jun"] & has["price_mar"] & ~has["price_sep"], "coverage"] = "two: June + March"
r.loc[has["price_jun"] & ~has["price_mar"] & has["price_sep"], "coverage"] = "two: June + September"
r.loc[has.all(axis=1), "coverage"] = "all three"
coverage = r["coverage"].value_counts().rename("listings").to_frame()
coverage["% of scope"] = (100 * coverage["listings"] / len(r)).round(1)
coverage.to_csv(config.OUTPUTS / "04_rate_coverage.csv")
print("\nCoverage of in-scope listings\n", coverage.to_string())

# ==========================================================================
# 3. Listings in all three: rate = mean of the three prices
# ==========================================================================
# Mean per listing (not median of three): each season counts equally, and with
# only three values the median would simply pick the middle season.
three = r[r["coverage"] == "all three"].copy()
three["rate_3"] = three[["price_mar", "price_jun", "price_sep"]].mean(axis=1)
three["ratio"] = three["rate_3"] / three["price_jun"]      # three-season average / June
three["ratio_mar"] = three["price_mar"] / three["price_jun"]  # March / June, for the low scenario
three["core"] = three["neighbourhood_cleansed"].isin(config.WORLD_CUP_CORE_AREAS)


def medians(d):
    """Medians across listings: robust to the few very expensive homes."""
    return pd.Series({"listings": len(d), "median_mar": d["price_mar"].median(),
                      "median_jun": d["price_jun"].median(), "median_sep": d["price_sep"].median(),
                      "median_3season_avg": round(d["rate_3"].median(), 2),
                      "median_ratio_avg_to_jun": round(d["ratio"].median(), 3)})


by_area = three.groupby("neighbourhood_cleansed").apply(medians).sort_values("listings", ascending=False)
by_area["small_n_flag"] = (by_area["listings"] < config.SMALL_N_THRESHOLD).map({True: "SMALL", False: ""})
overall = medians(three).to_frame("ALL AREAS").T
med = pd.concat([overall, by_area]).fillna({"small_n_flag": ""}).astype({"listings": int})
med.index.name = "neighbourhood"
med.to_csv(config.OUTPUTS / "04_rate_medians.csv")
print("\nMedian price by snapshot, listings priced in all three\n", med.to_string())

# Ratio = median of each listing's own (average / June), split by area to test
# whether one citywide ratio is fair to the stadium area.
ratio_tab = pd.DataFrame({"All areas": medians(three), "Downtown + West End": medians(three[three["core"]]),
                          "All other areas": medians(three[~three["core"]])}).T
ratio_tab["p25_ratio"] = [d["ratio"].quantile(.25).round(3) for d in (three, three[three["core"]], three[~three["core"]])]
ratio_tab["p75_ratio"] = [d["ratio"].quantile(.75).round(3) for d in (three, three[three["core"]], three[~three["core"]])]
ratio_tab = ratio_tab.astype({"listings": int}).rename_axis("group")
ratio_tab.to_csv(config.OUTPUTS / "04_rate_ratio.csv")
print("\nRatio: three-season average / June price\n", ratio_tab.to_string())
RATIO = float(three["ratio"].median())          # applied to June-only listings
RATIO_MAR = float(three["ratio_mar"].median())  # March level as a share of June

# ==========================================================================
# 4. Listings missing March or September: June price x overall ratio
# ==========================================================================
# Why not average the two prices they do have: June+March would lean low and
# June+September high, so listings would be treated differently depending on
# which file they happen to be missing from. One ratio treats them all alike.
r["rate_base"] = r[["price_mar", "price_jun", "price_sep"]].mean(axis=1).where(r["coverage"] == "all three")
adjust = r["price_jun"].notna() & (r["coverage"] != "all three")
r.loc[adjust, "rate_base"] = r.loc[adjust, "price_jun"] * RATIO
r["rate_adjusted"] = adjust
# Scenarios from decision log #5. Low = March level: the listing's own March
# price if it has one, otherwise June x the median March/June ratio.
r["rate_low"] = r["price_mar"].where(r["price_jun"].notna()).fillna(r["price_jun"] * RATIO_MAR)
r["rate_high"] = r["price_jun"]                      # June, unadjusted
n_rate = int(r["rate_base"].notna().sum())
print(f"\nRate from three snapshots: {len(three):,} | June x {RATIO:.3f} (rate_adjusted): {int(adjust.sum()):,} | "
      f"no rate (no usable June price): {len(r) - n_rate}")
scen = r[["rate_low", "rate_base", "rate_high"]].median().round(2)
print("Median nightly rate, all in-scope listings with a rate:", scen.to_dict())

# ==========================================================================
# 5. Save
# ==========================================================================
r.to_parquet(config.PROCESSED / "listings_rate.parquet", index=False)
note3 = "in-scope listings with a usable price (quote < 30 nights) in Mar, Jun and Sep 2026"
o, rt = overall.iloc[0], ratio_tab
record_key_numbers([
    ("rate_listings_all_three", int(o["listings"]), "listings", note3),
    ("rate_listings_adjusted", int(adjust.sum()), "listings", "June price x overall ratio (missing Mar or Sep)"),
    ("rate_listings_no_rate", len(r) - n_rate, "listings", "in scope but no usable June price"),
    ("rate_median_mar", o["median_mar"], "CAD/night", note3),
    ("rate_median_jun", o["median_jun"], "CAD/night", note3 + "; World Cup period"),
    ("rate_median_sep", o["median_sep"], "CAD/night", note3),
    ("rate_median_3season_avg", o["median_3season_avg"], "CAD/night", note3 + "; leans slightly high"),
    ("rate_ratio_avg_to_jun", round(RATIO, 3), "ratio", "median of per-listing (3-season avg / June)"),
    ("rate_ratio_avg_to_jun_core", rt.loc["Downtown + West End", "median_ratio_avg_to_jun"], "ratio", "Downtown + West End"),
    ("rate_ratio_avg_to_jun_other", rt.loc["All other areas", "median_ratio_avg_to_jun"], "ratio", "all other areas"),
    ("rate_ratio_mar_to_jun", round(RATIO_MAR, 3), "ratio", "median of per-listing (March / June); low scenario"),
    ("rate_base_median", scen["rate_base"], "CAD/night", "base case, all in-scope listings with a rate"),
    ("rate_low_median", scen["rate_low"], "CAD/night", "low scenario: March level"),
    ("rate_high_median", scen["rate_high"], "CAD/night", "high scenario: June unadjusted"),
], SCRIPT)
print("\n" + config.CREDIT_LINE_THREE_SNAPSHOTS)
