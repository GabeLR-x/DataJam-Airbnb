"""
03_scope_and_price.py: (1) cut the June listings down to STR comparables,
(2) check that the July 6 scrape group really is dormant, (3) measure how much
June prices sit above March prices on the SAME listings (World Cup check).

No revenue or return is modelled here. Outputs feed the nightly-rate choice.

Run:  python src/03_scope_and_price.py      (after 01_load_clean.py)
Out:  data/processed/listings_scope.parquet
      outputs/03_scope_counts.csv, 03_dormant_check.csv, 03_world_cup_price_check.csv
"""
import pandas as pd

import config
from common import record_key_numbers

SCRIPT = "03_scope_and_price.py"
keys = []
listings = pd.read_parquet(config.PROCESSED / "listings_clean.parquet")

# ==========================================================================
# 1. SCOPE FILTER
# ==========================================================================
# Each filter answers "is this listing comparable to what DDD would run?"
#  - entire home: DDD buys whole properties, not rooms in someone's home.
#  - minimum_nights < 30: 30+ nights is a mid-term rental, a different product.
#  - >= 1 review in the last 12 months: weakest evidence that it was actually
#    rented (reviews are a proxy for stays, not a count of them).
# A missing minimum_nights (5 listings) fails the test: we cannot show it is STR.
steps = {
    "0 all listings": pd.Series(True, index=listings.index),
    "1 entire home": listings["is_entire_home"],
    "2 + minimum_nights < 30": (listings["minimum_nights"] < config.MID_TERM_MIN_NIGHTS).fillna(False),
    f"3 + >= {config.MIN_REVIEWS_LTM} review in last 12 months":
        listings["number_of_reviews_ltm"] >= config.MIN_REVIEWS_LTM,
}
keep = pd.Series(True, index=listings.index)
counts = {}
for name, mask in steps.items():
    keep &= mask                      # filters are cumulative
    counts[name] = listings[keep].groupby("neighbourhood_cleansed").size()
    print(f"{name:42s} {int(keep.sum()):>6,} listings")
scope_counts = pd.DataFrame(counts).fillna(0).astype(int)
# How many in-scope listings also have a price (needed for any rate median).
scope_counts["4 ...of which have a price"] = (
    listings[keep & listings["price"].notna()].groupby("neighbourhood_cleansed").size())
scope_counts = scope_counts.fillna(0).astype(int).sort_values(scope_counts.columns[3], ascending=False)
scope_counts.loc["ALL AREAS"] = scope_counts.sum()
scope_counts.index.name = "neighbourhood"
scope_counts.to_csv(config.OUTPUTS / "03_scope_counts.csv")
print(scope_counts.to_string())

listings["in_scope"] = keep
scope = listings[keep]
scope.to_parquet(config.PROCESSED / "listings_scope.parquet", index=False)
n_small = int((scope_counts.iloc[:-1, 4] < config.SMALL_N_THRESHOLD).sum())
keys += [("scope_listings", len(scope), "listings",
          "entire home, minimum_nights < 30, >= 1 review in last 12 months"),
         ("scope_listings_with_price", int(scope["price"].notna().sum()), "listings", "in scope and priced"),
         ("scope_small_n_areas", n_small, "areas", f"< {config.SMALL_N_THRESHOLD} priced in-scope listings")]

# ==========================================================================
# 2. DORMANT CHECK: July 6 group vs June 15-16 groups
# ==========================================================================
# Why: a third of listings are "previous scrape" records re-visited on July 6.
# If the activity filter removes most of them on its own, we never need a
# separate (harder to defend) rule that drops them by scrape date.
listings["scrape_group"] = (listings["last_scraped"] == "2026-07-06").map(
    {True: "July 6 (previous scrape)", False: "June 15-16 (city scrape)"})
str_homes = listings["is_entire_home"] & steps["2 + minimum_nights < 30"]
dormant = listings.groupby("scrape_group").agg(
    all_listings=("id", "size"),
    entire_home_short_term=("is_entire_home", lambda s: int((s & str_homes[s.index]).sum())),
    in_scope=("in_scope", "sum"))
# Pass rate among short-term entire homes: isolates the ACTIVITY filter.
dormant["activity_pass_rate_%"] = (100 * dormant["in_scope"] / dormant["entire_home_short_term"]).round(1)
dormant["share_of_scope_%"] = (100 * dormant["in_scope"] / len(scope)).round(1)
dormant.to_csv(config.OUTPUTS / "03_dormant_check.csv")
print("\nDormant check\n", dormant.to_string())
july = dormant.loc["July 6 (previous scrape)"]
keys += [("july6_activity_pass_rate", july["activity_pass_rate_%"], "% of short-term entire homes",
          "July 6 scrape group; >= 1 review in last 12 months"),
         ("june_activity_pass_rate", dormant.loc["June 15-16 (city scrape)", "activity_pass_rate_%"],
          "% of short-term entire homes", "June 15-16 scrape groups"),
         ("july6_share_of_scope", july["share_of_scope_%"], "% of in-scope listings", "July 6 group left in scope")]

# ==========================================================================
# 3. WORLD CUP PRICE CHECK: same listing ids, March vs June
# ==========================================================================
# Load ONLY the non-private columns we need from the March file (privacy rule:
# host names, URLs and licence text are never read into memory here).
march = pd.read_csv(config.RAW_PRE_WORLDCUP / "listings.csv.gz", dtype=str,
                    usecols=["id", "price", "price_quote_checkin_date", "price_quote_checkout_date"])
march["price_mar"] = pd.to_numeric(march["price"].str.replace(r"[$,\s]", "", regex=True), errors="coerce")
mar_fail = int((march["price"].notna() & march["price_mar"].isna()).sum())
nights = (pd.to_datetime(march["price_quote_checkout_date"], format=config.DATE_FORMAT, errors="coerce")
          - pd.to_datetime(march["price_quote_checkin_date"], format=config.DATE_FORMAT, errors="coerce"))
march["nights_mar"] = nights.dt.days
print(f"\nMarch listings: {len(march):,}; price parse failures: {mar_fail}")

# Matching on id compares each home with itself, so the change is not caused by
# a different MIX of listings. Both quotes must be for stays under 30 nights:
# a monthly rate per night vs a nightly rate would be a fake price change.
m = listings.merge(march[["id", "price_mar", "nights_mar"]], on="id", how="inner")
print(f"Ids in both snapshots: {len(m):,}")
m = m[m["price"].notna() & m["price_mar"].notna()]
print(f"...both priced: {len(m):,}")
m = m[(m["price_quote_nights"] < config.MID_TERM_MIN_NIGHTS) & (m["nights_mar"] < config.MID_TERM_MIN_NIGHTS)]
print(f"...both quotes under {config.MID_TERM_MIN_NIGHTS} nights: {len(m):,}")
m["pct_change"] = 100 * (m["price"] / m["price_mar"] - 1)
m["core"] = m["neighbourhood_cleansed"].isin(config.WORLD_CUP_CORE_AREAS)
in_wc = m["price_quote_in_world_cup"].fillna(False)

# Median (not mean): a few listings repriced by several hundred % would drag a
# mean. The IQR shows how much listings disagree with the median.
groups = {
    "All matched listings": m,
    "Downtown + West End": m[m["core"]],
    "All other areas": m[~m["core"]],
    "In scope only": m[m["in_scope"]],
    "June quote inside World Cup window": m[in_wc],
    "June quote after the window": m[~in_wc],
}
wc = pd.DataFrame([{
    "group": g, "matched_listings": len(d),
    "median_price_mar": d["price_mar"].median(), "median_price_jun": d["price"].median(),
    "median_pct_change": round(d["pct_change"].median(), 1),
    "p25_pct_change": round(d["pct_change"].quantile(0.25), 1),
    "p75_pct_change": round(d["pct_change"].quantile(0.75), 1),
    "share_price_up_%": round(100 * (d["pct_change"] > 0).mean(), 1),
} for g, d in groups.items()])
wc.to_csv(config.OUTPUTS / "03_world_cup_price_check.csv", index=False)
print("\nMarch -> June price change on matched listings (includes normal spring->summer seasonality)")
print(wc.to_string(index=False))

note = "Mar 21 -> Jun 2026, same listing ids, both quotes < 30 nights; World Cup + seasonality, not WC alone"
row = wc.set_index("group")
keys += [("wc_matched_listings", len(m), "listings", note),
         ("wc_median_pct_change_all", row.loc["All matched listings", "median_pct_change"], "%", note),
         ("wc_median_pct_change_core", row.loc["Downtown + West End", "median_pct_change"], "%", note),
         ("wc_median_pct_change_other", row.loc["All other areas", "median_pct_change"], "%", note),
         ("wc_median_pct_change_in_scope", row.loc["In scope only", "median_pct_change"], "%", note),
         ("wc_median_pct_change_quote_after_window", row.loc["June quote after the window", "median_pct_change"],
          "%", "same match; June quote dated after Jul 7 (seasonality without the event; different listings)")]
record_key_numbers(keys, SCRIPT)
print("\n" + config.CREDIT_LINE_WITH_MARCH)
