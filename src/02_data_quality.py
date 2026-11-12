"""
02_data_quality.py: write outputs/data_quality_report.md for the June snapshot.

Why this exists: before any revenue or return number is built, we need to know
which fields can carry weight and which cannot. Each section below ends in a
"so what" for the analysis. Nothing is modelled or filtered here; this is a
description of the cleaned data from 01_load_clean.py.

Privacy: only aggregates are written. No host ids, names, licence numbers or
URLs appear in the report (they were dropped in 01; host_id is never printed).

Run:  python src/02_data_quality.py      (after 01_load_clean.py)
Out:  outputs/data_quality_report.md
      outputs/dq_listings_per_neighbourhood.csv
"""
import pandas as pd

import config
from common import md_table, record_key_numbers

SCRIPT = "02_data_quality.py"

listings = pd.read_parquet(config.PROCESSED / "listings_clean.parquet")
calendar = pd.read_parquet(config.PROCESSED / "calendar_clean.parquet")
reviews = pd.read_parquet(config.PROCESSED / "reviews_clean.parquet")
clean_log = pd.read_csv(config.OUTPUTS / "01_cleaning_log.csv")
parse_fail = pd.read_csv(config.OUTPUTS / "01_parse_failures.csv")

N = len(listings)
out = []    # markdown lines
keys = []   # rows for key_numbers.csv


def pct(x, d=1):
    """Format a share (0-1) as a percentage string."""
    return f"{100 * x:.{d}f}%"


def section(title):
    out.extend(["", f"## {title}", ""])


out += [
    "# Data quality report: Inside Airbnb Vancouver, June 2026 snapshot",
    "",
    f"*{config.CREDIT_LINE}*",
    "",
    "Produced by `src/02_data_quality.py` from the cleaned files written by "
    "`src/01_load_clean.py`. Nothing here is a model output, and no listing has "
    "been filtered out. All figures are aggregates.",
]

# --------------------------------------------------------------------------
# 0. Row counts through cleaning
# --------------------------------------------------------------------------
# Why: shows that cleaning removed no listings, and exactly which calendar /
# review rows were dropped and why.
section("0. Row counts at every cleaning step")
out.append(md_table(clean_log.fillna("")))

# --------------------------------------------------------------------------
# 1. Missing values in key columns
# --------------------------------------------------------------------------
# Why: a field that is missing for a non-random subset biases any median built
# on it. So we show missingness overall AND for entire homes (our likely scope).
section("1. Missing values in key columns")
key_cols = ["price", "estimated_revenue_l365d", "estimated_occupancy_l365d",
            "number_of_reviews_ltm", "first_review", "minimum_nights", "room_type",
            "neighbourhood_cleansed", "property_type", "accommodates", "bedrooms",
            "beds", "bathrooms", "bathrooms_text", "latitude", "longitude",
            "calculated_host_listings_count", "has_availability",
            "price_quote_checkin_date", "review_scores_rating"]
entire = listings[listings["is_entire_home"]]
miss = pd.DataFrame({
    "column": key_cols,
    "missing (all)": [int(listings[c].isna().sum()) for c in key_cols],
    "% of all listings": [pct(listings[c].isna().mean()) for c in key_cols],
    "% of entire homes": [pct(entire[c].isna().mean()) for c in key_cols],
})
out.append(md_table(miss))
out += ["",
        f"Licence text was missing for {int((~listings['licence_filled']).sum()):,} listings "
        f"({pct((~listings['licence_filled']).mean())}); see section 8.",
        "",
        "Columns that are 100% empty in our download and were removed in 01 "
        "(so they cannot be used): `host_since`, `host_response_time`, "
        "`host_response_rate`, `host_acceptance_rate`, `host_neighbourhood`, "
        "`host_total_listings_count`, `host_verifications`, `neighbourhood`, "
        "`neighbourhood_group_cleansed`, `neighborhood_overview`, `calendar_updated`, "
        "`instant_bookable`."]

# Is price missing at random? Compare by scrape date and by review activity.
# Why: if the listings without a price are the inactive ones, dropping them is
# harmless; if they are a different kind of listing, medians shift.
price_miss_by_scrape = (listings.assign(scraped=listings["last_scraped"].dt.date.astype(str))
                        .groupby("scraped")["price"]
                        .agg(listings="size", price_missing=lambda s: int(s.isna().sum())))
price_miss_by_scrape["% missing"] = (price_miss_by_scrape["price_missing"]
                                     / price_miss_by_scrape["listings"]).map(pct)
out += ["", "**Price missingness is not random.** By scrape date:", "",
        md_table(price_miss_by_scrape, index=True)]
no_price = listings["price"].isna()
out += ["",
        f"Listings without a price: median reviews in the last 12 months = "
        f"{listings.loc[no_price, 'number_of_reviews_ltm'].median():.0f} "
        f"(with a price: {listings.loc[~no_price, 'number_of_reviews_ltm'].median():.0f}); "
        f"{pct((listings.loc[no_price, 'number_of_reviews_ltm'] == 0).mean())} of them had "
        f"no review in the last 12 months "
        f"(with a price: {pct((listings.loc[~no_price, 'number_of_reviews_ltm'] == 0).mean())}).",
        f"`estimated_revenue_l365d` is missing for exactly the same listings as `price` "
        f"in {pct((listings['estimated_revenue_l365d'].isna() == no_price).mean())} of rows: "
        "Inside Airbnb's revenue estimate is built from `price`, so it inherits "
        "both its gaps and any event inflation."]
keys.append(("price_missing_share", round(100 * no_price.mean(), 1), "% of listings",
             "June snapshot, all listings"))

# --------------------------------------------------------------------------
# 2. Price: parse failures, what the price actually is, outliers
# --------------------------------------------------------------------------
section("2. Price: parse failures, what it measures, outliers")
n_price_fail = int(listings["price_parse_failed"].sum())
out += [f"- Price text present: {int(listings['price'].notna().sum()) + n_price_fail:,}; "
        f"parsed to a number: {int(listings['price'].notna().sum()):,}; "
        f"**parse failures: {n_price_fail}**; missing in the source: {int(no_price.sum()) - n_price_fail:,}.",
        "- Parse failures in every parsed field (from 01):", "",
        md_table(parse_fail)]

# What `price` measures. Why this matters: the field is a quote for ONE stay
# starting on price_quote_checkin_date, not a year-round nightly rate.
priced = listings[listings["price"].notna()]
in_wc = priced["price_quote_in_world_cup"]
long_quote = priced["price_quote_nights"] >= config.MID_TERM_MIN_NIGHTS
out += ["",
        "**What `price` is.** In this download `price` equals "
        "`price_quote_price_per_night`: the per-night price of one quoted stay "
        "that starts on `price_quote_checkin_date`. It is not an average rate "
        "for the year.",
        "",
        f"- Quoted check-in date falls inside the World Cup window "
        f"({config.WORLD_CUP_START} to {config.WORLD_CUP_END}) for "
        f"**{int(in_wc.sum()):,} of {len(priced):,} priced listings ({pct(in_wc.mean())})**.",
        f"- Quoted stay length: median {priced['price_quote_nights'].median():.0f} nights; "
        f"{int((priced['price_quote_nights'] == 1).sum()):,} quotes are for 1 night; "
        f"**{int(long_quote.sum()):,} ({pct(long_quote.mean())}) are for stays of "
        f"{config.MID_TERM_MIN_NIGHTS}+ nights** (a monthly rate spread per night, "
        "not a short-term nightly price)."]

# Median price by where the quoted night falls. Descriptive only: the groups
# differ in more than the date (see caveat), so this is NOT the World Cup
# premium. That is measured later on matched listing ids across snapshots.
str_priced = priced[priced["is_entire_home"] & ~priced["is_mid_term"].fillna(False)]
grp = (str_priced.assign(quote=str_priced["price_quote_in_world_cup"]
                         .map({True: "inside World Cup window", False: "outside window"}))
       .groupby("quote")["price"].agg(listings="size", median_price="median"))
grp["median_price"] = grp["median_price"].map(lambda v: f"${v:,.0f}")
out += ["",
        "Median price by quote date, entire homes with `minimum_nights` < "
        f"{config.MID_TERM_MIN_NIGHTS} (descriptive, NOT a causal premium: listings "
        "quoted outside the window are a different mix of listings):", "",
        md_table(grp, index=True)]

# Outliers. Flag, do not remove: removal is a decision for the log.
q = priced["price"].quantile([0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
qt = pd.DataFrame({"percentile": [f"p{int(p * 100)}" for p in q.index],
                   "price": [f"${v:,.0f}" for v in q.values]})
low = priced["price"] < config.PRICE_FLAG_LOW
high = priced["price"] > config.PRICE_FLAG_HIGH
out += ["", "**Distribution and outliers** (all priced listings, nothing removed):", "",
        md_table(qt), "",
        f"- Min ${priced['price'].min():,.2f}, max ${priced['price'].max():,.0f}.",
        f"- Below ${config.PRICE_FLAG_LOW}/night: {int(low.sum())} listings, of which "
        f"{int((low & long_quote).sum())} are {config.MID_TERM_MIN_NIGHTS}+ night quotes.",
        f"- Above ${config.PRICE_FLAG_HIGH:,}/night: {int(high.sum())} listings.",
        "- Thresholds are flags set in `config.py` (assumption), not filters."]
keys += [
    ("price_parse_failures", n_price_fail, "listings", "price text that did not parse"),
    ("price_quote_in_world_cup_share", round(100 * in_wc.mean(), 1), "% of priced listings",
     "quoted check-in date within Jun 13 - Jul 7, 2026"),
    ("price_quote_30plus_nights_share", round(100 * long_quote.mean(), 1), "% of priced listings",
     "price is a per-night figure from a 30+ night quote"),
    ("price_median_all_priced", round(float(priced["price"].median()), 0), "CAD/night",
     "all priced listings, unfiltered, World Cup period; not a 2027 rate"),
]

# --------------------------------------------------------------------------
# 3. minimum_nights
# --------------------------------------------------------------------------
# Why: 30+ night minimums are mid-term rentals, legally and commercially a
# different product. We need to know how much of the "supply" they are.
section("3. `minimum_nights` distribution")
bins = [0, 1, 2, 3, 6, 29, 30, 89, 10_000]
labels = ["1", "2", "3", "4-6", "7-29", "30", "31-89", "90+"]
mn = pd.cut(listings["minimum_nights"].astype("float"), bins=bins, labels=labels)
mn_tab = pd.DataFrame({
    "all listings": mn.value_counts().reindex(labels),
    "entire homes": mn[listings["is_entire_home"]].value_counts().reindex(labels),
})
mn_tab["% of all"] = (mn_tab["all listings"] / N).map(pct)
mn_tab.index.name = "minimum_nights"
out.append(md_table(mn_tab, index=True))
n_mid = int(listings["is_mid_term"].sum())
n_mn_missing = int(listings["minimum_nights"].isna().sum())
out += ["",
        f"- Missing `minimum_nights`: {n_mn_missing} listings.",
        f"- **{n_mid:,} listings ({pct(n_mid / N)}) have a minimum of "
        f"{config.MID_TERM_MIN_NIGHTS}+ nights**: mid-term rentals, not STR comparables "
        "(candidates for mid-term price comparables in the hybrid test).",
        f"- Entire homes with `minimum_nights` < {config.MID_TERM_MIN_NIGHTS}: "
        f"**{int((listings['is_entire_home'] & (listings['minimum_nights'] < config.MID_TERM_MIN_NIGHTS)).sum()):,}** "
        "(before any activity filter)."]
keys.append(("mid_term_listings_share", round(100 * n_mid / N, 1), "% of listings",
             "minimum_nights >= 30"))

# --------------------------------------------------------------------------
# 4. Room types
# --------------------------------------------------------------------------
section("4. Room types")
rt = listings["room_type"].value_counts().rename("listings").to_frame()
rt["% of all"] = (rt["listings"] / N).map(pct)
rt["of which min_nights >= 30"] = listings[listings["is_mid_term"].fillna(False)]["room_type"] \
    .value_counts().reindex(rt.index).fillna(0).astype(int)
rt.index.name = "room_type"
out.append(md_table(rt, index=True))

# --------------------------------------------------------------------------
# 5. Listings per neighbourhood
# --------------------------------------------------------------------------
# Why: area medians need enough listings behind them. We show the count that
# will actually be usable (entire home, short-term, with a price), and flag
# small areas.
section("5. Listings per neighbourhood")
strm = listings["is_entire_home"] & (listings["minimum_nights"] < config.MID_TERM_MIN_NIGHTS).fillna(False)
nb = listings.groupby("neighbourhood_cleansed").agg(all_listings=("id", "size"))
nb["entire_home"] = listings[listings["is_entire_home"]].groupby("neighbourhood_cleansed").size()
nb["entire_home_short_term"] = listings[strm].groupby("neighbourhood_cleansed").size()
nb["...with a price"] = listings[strm & listings["price"].notna()].groupby("neighbourhood_cleansed").size()
nb = nb.fillna(0).astype(int).sort_values("all_listings", ascending=False)
nb["small_n_flag"] = (nb["...with a price"] < config.SMALL_N_THRESHOLD).map({True: "SMALL", False: ""})
nb.index.name = "neighbourhood"
nb.to_csv(config.OUTPUTS / "dq_listings_per_neighbourhood.csv")
out.append(md_table(nb, index=True))
n_small = int((nb["small_n_flag"] == "SMALL").sum())
out += ["",
        f"- {len(nb)} neighbourhood names (the City has 22 local areas; Inside Airbnb "
        "adds \"Downtown Eastside\"). Any join to City open data needs an explicit mapping.",
        f"- Top 3 areas hold {pct(nb['all_listings'].head(3).sum() / N)} of all listings.",
        f"- **{n_small} areas have fewer than {config.SMALL_N_THRESHOLD} priced, short-term "
        "entire homes** (flagged SMALL): too few to rank on a median without a wide range.",
        f"- \"Entire home, short-term\" = `room_type` entire home/apt and `minimum_nights` < "
        f"{config.MID_TERM_MIN_NIGHTS}; no activity filter applied yet."]
keys.append(("neighbourhoods_small_n", n_small, "areas",
             f"< {config.SMALL_N_THRESHOLD} priced short-term entire homes"))

# --------------------------------------------------------------------------
# 6. last_scraped split
# --------------------------------------------------------------------------
# Why: "last 365 days" and "next 365 days" start on a different day for each
# group, and the July 6 group is a different kind of record ("previous scrape").
section("6. `last_scraped` split")
ls = (listings.assign(scraped=listings["last_scraped"].dt.date.astype(str))
      .groupby(["scraped", "source"])
      .agg(listings=("id", "size"),
           price_missing=("price", lambda s: pct(s.isna().mean())),
           no_reviews_ltm=("number_of_reviews_ltm", lambda s: pct((s == 0).mean())),
           median_reviews_ltm=("number_of_reviews_ltm", "median"),
           median_availability_365=("availability_365", "median"))
      .reset_index())
ls.insert(3, "% of all", (ls["listings"] / N).map(pct))
out.append(md_table(ls))
cal_span = calendar.groupby("listing_id")["date"].agg(["min", "max"])
common_start, common_end = cal_span["min"].max(), cal_span["max"].min()
out += ["",
        f"- Every scrape date is inside the World Cup window ({config.WORLD_CUP_START} to "
        f"{config.WORLD_CUP_END}).",
        "- The July 6 group is 100% `source = previous scrape`: listings carried over from "
        "an earlier scrape and re-visited three weeks later. Their `*_l365d` / `*_ltm` "
        "windows and calendars start ~3 weeks later than the rest.",
        f"- Calendar dates run {calendar['date'].min().date()} to {calendar['date'].max().date()}. "
        f"Dates covered by every listing: **{common_start.date()} to {common_end.date()}** "
        f"({(common_end - common_start).days + 1} days). Compare listings on calendar date, "
        "not on \"days ahead\".",
        f"- Calendar coverage of 2027: through {calendar['date'].max().date()} only, so the "
        "calendar cannot describe the second half of DDD's measured year."]
keys.append(("scraped_july6_share", round(100 * (listings["last_scraped"] == "2026-07-06").mean(), 1),
             "% of listings", "source = previous scrape; later 365-day windows"))

# --------------------------------------------------------------------------
# 7. Calendar unavailable share (NOT occupancy)
# --------------------------------------------------------------------------
section("7. Calendar: share of nights unavailable (NOT occupancy)")
out += ["> **This is not an occupancy rate.** An unavailable night is either booked or "
        "blocked by the host; the data does not say which. Read every figure in this "
        "section as an **upper bound** on booked nights. The monthly table below shows "
        "why: the unavailable share is highest 9-12 months after the scrape, when very "
        "few guests have booked yet, so much of it must be hosts who have not opened "
        "their calendar that far ahead.", ""]
unavail = ~calendar["available"]
overall_unavail = unavail.mean()
per_listing = unavail.groupby(calendar["listing_id"]).mean()
fully_blocked = int((per_listing == 1).sum())
fully_open = int((per_listing == 0).sum())
out += [f"- Listing-nights: {len(calendar):,} across {calendar['listing_id'].nunique():,} listings.",
        f"- Unavailable: {int(unavail.sum()):,} nights = **{pct(overall_unavail)}** (upper bound "
        "on booked share, not occupancy).",
        f"- Listings unavailable on **every** night for a year: {fully_blocked:,} "
        f"({pct(fully_blocked / len(per_listing))}). These are almost certainly blocked or "
        "dormant, not fully booked, which shows why unavailable is not the same as booked.",
        f"- Listings available on every night: {fully_open:,} ({pct(fully_open / len(per_listing))}).",
        f"- Excluding the always-unavailable listings, the unavailable share is "
        f"{pct(unavail[~calendar['listing_id'].isin(per_listing[per_listing == 1].index)].mean())} "
        "(still an upper bound)."]
# By month, on the date range every listing covers, so each month compares the
# same set of listings.
common = calendar[(calendar["date"] >= common_start) & (calendar["date"] <= common_end)]
by_month = (~common["available"]).groupby(common["date"].dt.to_period("M")).agg(["size", "mean"])
by_month = by_month.rename(columns={"size": "listing-nights", "mean": "unavailable share (upper bound)"})
by_month["unavailable share (upper bound)"] = by_month["unavailable share (upper bound)"].map(pct)
by_month.index = by_month.index.astype(str)
by_month.index.name = "month"
out += ["", "Unavailable share by month, restricted to dates every listing covers "
        "(first and last months are partial):", "", md_table(by_month, index=True)]
keys.append(("calendar_unavailable_share", round(100 * overall_unavail, 1), "% of listing-nights",
             "UPPER BOUND on booked share; unavailable = booked OR host-blocked; NOT occupancy"))

# --------------------------------------------------------------------------
# 8. Licence-filled share (an estimate)
# --------------------------------------------------------------------------
section("8. Licence field (estimate, aggregates only)")
out += ["> **Estimate.** This is what hosts typed into the listing page, classified by "
        "pattern. It was not checked against the City of Vancouver licence register, a "
        "number can be invalid, expired or reused, and a blank field can be a scrape gap "
        "rather than an unlicensed listing. Licence numbers themselves were discarded in 01.", ""]
order = ["number", "exempt", "other", "missing"]
meaning = {"number": "text shaped like a City licence number",
           "exempt": "host wrote \"Exempt\"",
           "other": "other text (e.g. \"30 Day Minimum\")",
           "missing": "field empty"}
lic = listings["licence_municipal_status"].value_counts().reindex(order).rename("all listings").to_frame()
lic["% of all"] = (lic["all listings"] / N).map(pct)
lic["entire home, short-term"] = listings[strm]["licence_municipal_status"].value_counts().reindex(order)
lic["% of those"] = (lic["entire home, short-term"] / int(strm.sum())).map(pct)
lic.insert(0, "meaning", [meaning[i] for i in lic.index])
lic.index.name = "municipal licence field"
out.append(md_table(lic, index=True))
has_reviews = listings["number_of_reviews"] > 0
out += ["",
        f"- Licence field filled (any text): {int(listings['licence_filled'].sum()):,} = "
        f"**{pct(listings['licence_filled'].mean())}** of listings (estimate).",
        f"- `has_licence` (number-shaped text): {int(listings['has_licence'].sum()):,} = "
        f"**{pct(listings['has_licence'].mean())}** (estimate).",
        f"- Provincial registration number shown: "
        f"{int(listings['has_provincial_registration'].sum()):,} = "
        f"{pct(listings['has_provincial_registration'].mean())} (estimate).",
        f"- Among mid-term listings (`minimum_nights` >= {config.MID_TERM_MIN_NIGHTS}), which "
        f"do not need an STR licence: field empty for "
        f"{pct((~listings.loc[listings['is_mid_term'].fillna(False), 'licence_filled']).mean())}, "
        f"vs {pct((~listings.loc[strm, 'licence_filled']).mean())} for short-term entire homes.",
        f"- Field empty for {pct((~listings.loc[~has_reviews, 'licence_filled']).mean())} of "
        f"listings with no reviews vs {pct((~listings.loc[has_reviews, 'licence_filled']).mean())} "
        "of listings with reviews."]
keys += [
    ("licence_filled_share", round(100 * listings["licence_filled"].mean(), 1), "% of listings",
     "ESTIMATE: any text in the licence field; not verified against the City register"),
    ("has_licence_share", round(100 * listings["has_licence"].mean(), 1), "% of listings",
     "ESTIMATE: text shaped like a municipal licence number; not verified"),
]

# --------------------------------------------------------------------------
# 9. Join integrity
# --------------------------------------------------------------------------
section("9. Join integrity: ids not in listings")
def dropped(table):
    row = clean_log[(clean_log["table"] == table) & clean_log["step"].str.contains("not in listings")]
    return row["note"].iloc[0]
out += [f"- Calendar ids not in listings: **{dropped('calendar')}** dropped in 01 "
        "(no room type, area or price to join to).",
        f"- Review listing ids not in listings: {dropped('reviews')} dropped in 01.",
        f"- Listings with no calendar rows: {int((~listings['id'].isin(calendar['listing_id'])).sum())}.",
        f"- Listings with no review rows: {int((~listings['id'].isin(reviews['listing_id'])).sum()):,} "
        f"(listings reporting `number_of_reviews` = 0: {int((listings['number_of_reviews'] == 0).sum()):,}).",
        f"- Nights per listing in calendar: "
        f"{calendar.groupby('listing_id').size().value_counts().to_dict()} (nights: listings).",
        f"- Reviews run {reviews['date'].min().date()} to {reviews['date'].max().date()}. "
        "Reviews are a proxy for stays, not a count of them."]

out += ["", "---", f"*{config.CREDIT_LINE}*", ""]
(config.OUTPUTS / "data_quality_report.md").write_text("\n".join(out))
record_key_numbers(keys, SCRIPT)
print("\n".join(out))
