"""
05_revenue.py: estimated annual revenue per in-scope listing
= estimated nights booked x nightly rate (from script 04).

Nights booked are NOT observed. They are estimated from reviews (a proxy for
stays): reviews in the last 12 months / review rate x nights per stay, capped.
Step 1 shows Inside Airbnb's `estimated_occupancy_l365d` is exactly that
calculation with the constants in config.py, so the base case uses the field.

Not used: calendar availability. An unavailable night may be booked or blocked
by the host, and `availability_365` looks 365 days FORWARD while reviews look
365 days BACK, so "365 - availability_365" is not a bound on past bookings.
No costs or returns here.

Run:  python src/05_revenue.py      (after 04_nightly_rate.py)
Out:  data/processed/listings_revenue.parquet
      outputs/05_revenue_by_neighbourhood.csv / .png, 05_revenue_by_bedrooms.csv,
      05_revenue_sensitivity.csv
"""
import matplotlib
matplotlib.use("Agg")  # write the PNG without opening a window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config
from common import record_key_numbers

SCRIPT = "05_revenue.py"

scope = pd.read_parquet(config.PROCESSED / "listings_scope.parquet")
rate = pd.read_parquet(config.PROCESSED / "listings_rate.parquet")
d = scope[["id", "neighbourhood_cleansed", "bedrooms", "number_of_reviews_ltm", "minimum_nights",
           "estimated_occupancy_l365d", "estimated_revenue_l365d"]].merge(
    rate[["id", "rate_low", "rate_base", "rate_high", "rate_adjusted"]], on="id", how="left")
assert len(d) == len(scope), "The merge duplicated listings."


# ---- 1. What is estimated_occupancy_l365d? Re-derive it and compare. ----
def nights_from_reviews(review_rate):
    """Estimated nights booked in the last 12 months.

    stays = reviews / review rate (not every guest leaves a review);
    nights = stays x nights per stay (3, or the listing's minimum stay if
    that is longer); capped so no listing is credited more than 70% of a year.
    """
    stays = d["number_of_reviews_ltm"] / review_rate
    per_stay = d["minimum_nights"].clip(lower=config.AVG_STAY_NIGHTS)
    return (stays * per_stay).clip(upper=config.MAX_NIGHTS_PER_YEAR).astype(float)


ours = nights_from_reviews(config.REVIEW_RATE)
match = float(np.isclose(ours, d["estimated_occupancy_l365d"]).mean())
print(f"In-scope listings: {len(d):,}")
print(f"estimated_occupancy_l365d: min {d['estimated_occupancy_l365d'].min()}, "
      f"max {d['estimated_occupancy_l365d'].max()} nights")
print(f"Our formula (reviews / {config.REVIEW_RATE} x max({config.AVG_STAY_NIGHTS}, minimum_nights), "
      f"cap {config.MAX_NIGHTS_PER_YEAR}) equals it for {100 * match:.1f}% of listings")
# If this ever fails (new download, changed method) we must stop and re-decide.
assert match == 1.0, "Inside Airbnb's occupancy no longer matches our constants."

# ---- 2. Nights booked: base case + review-rate sensitivity ----
d["nights_base"] = d["estimated_occupancy_l365d"].astype(float)   # = ours, shown above
d["nights_low"] = nights_from_reviews(config.REVIEW_RATE_HIGH)    # 72% review -> fewer stays
d["nights_high"] = nights_from_reviews(config.REVIEW_RATE_LOW)    # 30.5% review -> more stays
capped = float((d["nights_base"] >= config.MAX_NIGHTS_PER_YEAR).mean())
print(f"Median nights: low {d['nights_low'].median():.0f} | base {d['nights_base'].median():.0f} "
      f"| high {d['nights_high'].median():.0f}; at the cap in base: {100 * capped:.1f}%")

# ---- 3. Estimated revenue = nights x nightly rate ----
d["revenue_base"] = d["nights_base"] * d["rate_base"]
d["revenue_rate_low"] = d["nights_base"] * d["rate_low"]      # March-level rate
d["revenue_rate_high"] = d["nights_base"] * d["rate_high"]    # June rate as it is
d["revenue_nights_low"] = d["nights_low"] * d["rate_base"]
d["revenue_nights_high"] = d["nights_high"] * d["rate_base"]
rev = d[d["revenue_base"].notna()]     # listings with no usable June price have no rate
print(f"Listings with estimated revenue: {len(rev):,} (no rate: {len(d) - len(rev)})")

# ---- 4. Checks ----
# 4a. Against Inside Airbnb's own estimate (their nights x the JUNE price).
# Nights are identical, so the ratio should equal our rate / June price.
both = rev[rev["estimated_revenue_l365d"] > 0]
ratio = both["revenue_base"] / both["estimated_revenue_l365d"]
print(f"4a. Ours / Inside Airbnb estimate, {len(both):,} listings: median {ratio.median():.3f} "
      f"(p25 {ratio.quantile(.25):.3f}, p75 {ratio.quantile(.75):.3f})")
# 4b. Sensitivity table: median estimated revenue under each single change.
cases = {"base": "revenue_base", "nightly rate low (March level)": "revenue_rate_low",
         "nightly rate high (June as it is)": "revenue_rate_high",
         f"review rate {config.REVIEW_RATE_HIGH:.0%} (fewer nights)": "revenue_nights_low",
         f"review rate {config.REVIEW_RATE_LOW:.1%} (more nights)": "revenue_nights_high"}
sens = pd.DataFrame({"median_estimated_revenue": {k: rev[c].median() for k, c in cases.items()}})
sens["vs_base_pct"] = (100 * (sens["median_estimated_revenue"] / sens.loc["base", "median_estimated_revenue"] - 1)).round(1)
sens["median_estimated_revenue"] = sens["median_estimated_revenue"].round(0).astype(int)
sens.rename_axis("case").to_csv(config.OUTPUTS / "05_revenue_sensitivity.csv")
print("\n4b. Sensitivity\n", sens.to_string())


# ---- 5. Tables and chart ----
def summary(by):
    """Median and middle half (p25-p75): robust to a few very large homes."""
    t = rev.groupby(by)["revenue_base"].agg(
        n="size", median="median", p25=lambda s: s.quantile(.25), p75=lambda s: s.quantile(.75))
    t[["median", "p25", "p75"]] = t[["median", "p25", "p75"]].round(0).astype(int)   # no cents
    t["small_n_flag"] = (t["n"] < config.SMALL_N_THRESHOLD).map({True: "SMALL", False: ""})
    return t


by_area = summary("neighbourhood_cleansed").sort_values("median", ascending=False).rename_axis("neighbourhood")
by_area.to_csv(config.OUTPUTS / "05_revenue_by_neighbourhood.csv")
# 5+ bedrooms are pooled (few listings); listings with no bedroom count are left out.
beds = rev["bedrooms"].clip(upper=5).astype("Int64").astype(str).replace({"5": "5+", "<NA>": pd.NA})
by_beds = summary(beds.rename("bedrooms"))
by_beds.to_csv(config.OUTPUTS / "05_revenue_by_bedrooms.csv")
print("\nBy neighbourhood\n", by_area.to_string(), "\n\nBy bedrooms\n", by_beds.to_string())

# Dot = median, line = p25 to p75. Grey = fewer than 30 listings (do not rank on these).
c = by_area.iloc[::-1]
colour = np.where(c["small_n_flag"] == "SMALL", "#9a9a9a", "#1f5fa8")
fig, ax = plt.subplots(figsize=(9, 8))
ax.hlines(range(len(c)), c["p25"], c["p75"], color=colour, lw=2, alpha=.55)
ax.scatter(c["median"], range(len(c)), color=colour, s=45, zorder=3)
ax.set_yticks(range(len(c)), [f"{a} (n={n})" + (" *" if f else "") for a, n, f in zip(c.index, c["n"], c["small_n_flag"])])
ax.xaxis.set_major_formatter(lambda x, _: f"${x / 1000:.0f}k")
ax.set_xlabel("Estimated revenue per listing, last 12 months, at our base nightly rate (CAD)")
ax.set_title("Estimated annual revenue by neighbourhood\nDot = median listing, line = middle half (p25 to p75)",
             loc="left", fontsize=12)
ax.grid(axis="x", color="#e5e5e5", zorder=0)
ax.spines[["top", "right", "left"]].set_visible(False)
fig.text(0.01, 0.01, f"* grey: fewer than {config.SMALL_N_THRESHOLD} listings, too few to rank. Estimates from reviews "
         f"and asking prices, not reported income.\n{config.CREDIT_LINE_WITH_MARCH}", fontsize=8, color="#555555")
fig.tight_layout(rect=(0, 0.05, 1, 1))
fig.savefig(config.OUTPUTS / "05_revenue_by_neighbourhood.png", dpi=200)

# ---- 6. Save ----
d.drop(columns=["estimated_occupancy_l365d"]).to_parquet(config.PROCESSED / "listings_revenue.parquet", index=False)
m = sens["median_estimated_revenue"]
record_key_numbers([
    ("occupancy_formula_match_share", round(100 * match, 1), "% of in-scope listings", "our constants reproduce Inside Airbnb estimated_occupancy_l365d"),
    ("nights_base_median", d["nights_base"].median(), "nights/yr", "estimated from reviews; review rate 50%"),
    ("nights_low_median", round(d["nights_low"].median(), 0), "nights/yr", "review rate 72%"),
    ("nights_high_median", round(d["nights_high"].median(), 0), "nights/yr", "review rate 30.5%"),
    ("nights_capped_share", round(100 * capped, 1), "% of in-scope listings", "at the 255-night cap in the base case"),
    ("revenue_listings", len(rev), "listings", "in scope with a nightly rate"),
    ("revenue_base_median", m["base"], "CAD/yr", "estimated revenue per listing, base case"),
    ("revenue_base_p25", int(round(rev["revenue_base"].quantile(.25))), "CAD/yr", "base case"),
    ("revenue_base_p75", int(round(rev["revenue_base"].quantile(.75))), "CAD/yr", "base case"),
    ("revenue_rate_low_median", m.iloc[1], "CAD/yr", "base nights x March-level rate"),
    ("revenue_rate_high_median", m.iloc[2], "CAD/yr", "base nights x June rate"),
    ("revenue_nights_low_median", m.iloc[3], "CAD/yr", "review rate 72% x base rate"),
    ("revenue_nights_high_median", m.iloc[4], "CAD/yr", "review rate 30.5% x base rate"),
    ("revenue_ratio_to_inside_airbnb", round(ratio.median(), 3), "ratio", "median of per-listing (ours / estimated_revenue_l365d)"),
], SCRIPT)
print("\n" + config.CREDIT_LINE_WITH_MARCH)
