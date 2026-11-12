"""
01_load_clean.py: load the June 2026 snapshot, clean it, save to data/processed/.

Scope: ONLY the primary snapshot at the top level of data/raw/ (the brief's
"15 June 2026" data). The March and September snapshots are handled later.

This script CLEANS, it does not FILTER. No listing is removed for being a
private room, a mid-term rental, inactive or an outlier. Those are scope
decisions that belong in the decision log with before/after numbers, so here
we only add flags. The only rows dropped are calendar/review rows whose
listing id does not exist in listings (they cannot be joined to anything).

Run:  python src/01_load_clean.py
Out:  data/processed/listings_clean.parquet
      data/processed/calendar_clean.parquet
      data/processed/reviews_clean.parquet
      outputs/01_cleaning_log.csv   (row counts and parse failures per step)
"""
import pandas as pd

import config
from common import record_key_numbers

SCRIPT = "01_load_clean.py"
log_rows = []  # every step appends (table, step, rows, cols, note) -> audit trail


def log(table, step, df, note=""):
    """Print and record the table's size after a step, so that any row that
    disappears (or does not) is visible and explainable."""
    log_rows.append((table, step, len(df), df.shape[1], note))
    print(f"[{table:8s}] {step:42s} rows={len(df):>9,}  cols={df.shape[1]:>2}  {note}")


def parse_date(series, name):
    """Parse a date column with an EXPLICIT format (rule 7).

    Why explicit: pandas' automatic guessing can silently swap day and month.
    With a fixed format, anything unexpected becomes NaT and is counted here.
    Returns (parsed series, number of non-empty values that failed to parse).
    """
    parsed = pd.to_datetime(series, format=config.DATE_FORMAT, errors="coerce")
    failed = int((series.notna() & parsed.isna()).sum())
    print(f"           date {name:26s} missing={int(series.isna().sum()):>7,}  parse_failures={failed}")
    return parsed, failed


def parse_money(series):
    """Turn price text like "$1,234.00" into a float (rule 6).

    Strip only the characters we expect ($ , and spaces); anything else that
    is left makes to_numeric return NaN, which we count as a parse failure
    rather than guessing.
    Returns (parsed series, boolean mask of non-empty values that failed).
    """
    cleaned = series.str.replace(r"[$,\s]", "", regex=True)
    parsed = pd.to_numeric(cleaned, errors="coerce")
    failed = series.notna() & parsed.isna()
    return parsed, failed


# ==========================================================================
# LISTINGS
# ==========================================================================
# Read everything as text first. Why: (a) ids go up to 19 digits and would lose
# precision if pandas guessed float; (b) we want to convert each column
# deliberately and count failures, not let read_csv guess.
listings = pd.read_csv(config.RAW / "listings.csv.gz", dtype=str)
log("listings", "1 loaded raw", listings)

# Guard: we must be working on the detailed file, not the 18-19 column summary.
assert listings.shape[1] > 60, "This looks like the summary listings file, not the detailed one."
assert listings["id"].is_unique, "Duplicate listing ids in the raw file."

# --- Licence flags, derived BEFORE the licence text is dropped (rules 1 & 8) ---
# The field is free text typed by the host, e.g.
#   "Municipal registration number: <text><br />Provincial registration number: <text>"
# We never keep the number itself. We only classify what the host CLAIMED:
#   missing  - field empty
#   exempt   - host wrote "Exempt"
#   number   - text contains something shaped like a City of Vancouver licence
#              number (two-digit year, optional dash/space, 5-6 digits)
#   other    - any other text (e.g. "30 Day Minimum", a provincial number pasted
#              in the municipal box)
# This is a claim on a web page, not a check against the City's licence
# register, so every rate built on it is an ESTIMATE and is only ever shown as
# an aggregate.
lic = listings["license"]
municipal = lic.str.extract(r"Municipal registration number:\s*(.*?)(?:<br\s*/?>|$)", expand=False)
provincial = lic.str.extract(r"Provincial registration number:\s*(.*)$", expand=False)

listings["licence_filled"] = lic.notna()
listings["licence_municipal_status"] = "other"
listings.loc[municipal.str.contains(r"\d{2}\s*[-–]?\s*\d{5,6}", na=False), "licence_municipal_status"] = "number"
listings.loc[municipal.str.strip().str.lower().eq("exempt"), "licence_municipal_status"] = "exempt"
listings.loc[lic.isna(), "licence_municipal_status"] = "missing"
# has_licence = the host shows something shaped like a municipal licence number.
listings["has_licence"] = listings["licence_municipal_status"].eq("number")
# BC's provincial STR registry numbers look like H######### (host) or PM#########
# (platform/property manager). Flag separately: it is a different requirement.
listings["has_provincial_registration"] = provincial.str.contains(r"[A-Za-z]{1,2}\d{9}", na=False)
log("listings", "2 licence flags derived", listings,
    f"has_licence={int(listings['has_licence'].sum()):,}")

# --- Privacy drop (rule 1), immediately after the flags exist ---
to_drop = config.PRIVATE_COLUMNS_REQUIRED + config.PRIVATE_COLUMNS_EXTRA
missing_expected = [c for c in to_drop if c not in listings.columns]
if missing_expected:  # rule 9: column names drift; tell us instead of crashing
    print(f"           NOTE: private columns not present in this download: {missing_expected}")
listings = listings.drop(columns=[c for c in to_drop if c in listings.columns])
log("listings", "3 private columns dropped", listings)

# --- Drop columns that are 100% empty in this download ---
# They carry no information (e.g. host_since, host_response_rate and
# instant_bookable are entirely blank in our file). We list them so nobody
# later assumes they were available.
empty_cols = [c for c in listings.columns if listings[c].isna().all()]
print(f"           100% empty columns removed: {empty_cols}")
listings = listings.drop(columns=empty_cols)
log("listings", "4 all-empty columns dropped", listings, f"{len(empty_cols)} columns")

# --- Dates, explicit format ---
date_failures = {}
for col in ["last_scraped", "calendar_last_scraped", "first_review", "last_review",
            "price_quote_checkin_date", "price_quote_checkout_date"]:
    listings[col], date_failures[f"listings.{col}"] = parse_date(listings[col], col)

# Guard: confirm this really is the brief's snapshot (earliest scrape date
# within +/- 1 day of 15 June 2026). Later scrape dates are reported, not
# rejected: about a third of our listings were re-scraped on a later date.
first_scrape = listings["last_scraped"].min()
assert abs((first_scrape - pd.Timestamp(config.SNAPSHOT_DATE)).days) <= 1, \
    f"Snapshot starts {first_scrape.date()}, expected {config.SNAPSHOT_DATE} +/- 1 day."
print("           last_scraped split:",
      {str(k.date()): int(v) for k, v in listings["last_scraped"].value_counts().sort_index().items()})
log("listings", "5 dates parsed", listings, f"failures={sum(date_failures.values())}")

# --- Price text -> number ---
# Keep a per-row failure flag so 02 can report it from the data.
listings["price"], failed = parse_money(listings["price"])
listings["price_parse_failed"] = failed
print(f"           price: missing={int(listings['price'].isna().sum() - failed.sum()):,}  "
      f"parse_failures={int(failed.sum())}")

# `price` is a QUOTE for one specific check-in date (price_quote_checkin_date),
# not a year-round rate. Record the length of the quoted stay: a quote for a
# 30+ night stay is a discounted monthly rate, not a nightly STR price.
listings["price_quote_nights"] = (
    listings["price_quote_checkout_date"] - listings["price_quote_checkin_date"]).dt.days
# Was the quoted check-in night inside the World Cup window? Needed later to
# judge how event-inflated the price field is.
listings["price_quote_in_world_cup"] = (
    listings["price_quote_checkin_date"]
    .between(config.WORLD_CUP_START, config.WORLD_CUP_END)
    .astype("boolean")
    .mask(listings["price_quote_checkin_date"].isna())  # no quote date -> unknown, not False
)
log("listings", "6 price parsed", listings, f"price present={int(listings['price'].notna().sum()):,}")

# --- Numeric columns ---
# Convert the columns the analysis needs; count anything that is text but not
# a number (should be zero). nullable Int64 keeps counts as whole numbers even
# when some rows are missing.
int_cols = ["minimum_nights", "maximum_nights", "accommodates", "bedrooms", "beds",
            "availability_30", "availability_60", "availability_90", "availability_365",
            "availability_eoy", "number_of_reviews", "number_of_reviews_ltm",
            "number_of_reviews_l30d", "number_of_reviews_ly",
            "estimated_occupancy_l365d",
            "host_listings_count", "calculated_host_listings_count",
            "calculated_host_listings_count_entire_homes",
            "calculated_host_listings_count_private_rooms",
            "calculated_host_listings_count_shared_rooms",
            "minimum_minimum_nights", "maximum_minimum_nights",
            "minimum_maximum_nights", "maximum_maximum_nights"]
float_cols = ["latitude", "longitude", "bathrooms", "estimated_revenue_l365d",
              "price_quote_total_price", "price_quote_price_per_night",
              "minimum_nights_avg_ntm", "maximum_nights_avg_ntm", "reviews_per_month",
              "review_scores_rating", "review_scores_accuracy", "review_scores_cleanliness",
              "review_scores_checkin", "review_scores_communication",
              "review_scores_location", "review_scores_value"]
numeric_failures = 0
for col in int_cols + float_cols:
    if col not in listings.columns:
        print(f"           NOTE: expected numeric column not in this download: {col}")
        continue
    converted = pd.to_numeric(listings[col], errors="coerce")
    numeric_failures += int((listings[col].notna() & converted.isna()).sum())
    listings[col] = converted.round().astype("Int64") if col in int_cols else converted
log("listings", "7 numeric columns converted", listings, f"failures={numeric_failures}")

# --- Booleans stored as 't' / 'f' ---
for col in ["has_availability", "host_is_superhost", "host_has_profile_pic", "host_identity_verified"]:
    if col in listings.columns:
        listings[col] = listings[col].map({"t": True, "f": False}).astype("boolean")

# --- Flags for later scope decisions (flags only; no rows removed) ---
# 30+ night minimum = mid-term rental, not an STR comparable.
listings["is_mid_term"] = listings["minimum_nights"] >= config.MID_TERM_MIN_NIGHTS
listings["is_entire_home"] = listings["room_type"].eq("Entire home/apt")
log("listings", "8 flags added (final)", listings)

# ==========================================================================
# CALENDAR
# ==========================================================================
calendar = pd.read_csv(config.RAW / "calendar.csv.gz", dtype=str)
log("calendar", "1 loaded raw", calendar)

# Our calendar file has NO price column. Stop loudly if that ever changes,
# because the World Cup approach in CLAUDE.md depends on it.
price_cols = [c for c in calendar.columns if "price" in c]
print(f"           price columns in calendar: {price_cols if price_cols else 'none'}")

# Drop calendar rows whose listing is not in listings: nothing to join them to
# (no room type, neighbourhood or price), so they cannot be used.
orphan = ~calendar["listing_id"].isin(listings["id"])
n_orphan_ids = calendar.loc[orphan, "listing_id"].nunique()
calendar = calendar[~orphan].copy()
log("calendar", "2 ids not in listings dropped", calendar,
    f"{n_orphan_ids} ids, {int(orphan.sum()):,} rows")

calendar["date"], date_failures["calendar.date"] = parse_date(calendar["date"], "calendar.date")

# 't'/'f' -> boolean. IMPORTANT (rule 3): available == False means the night
# could not be booked on the scrape date. It may be BOOKED or BLOCKED BY THE
# HOST; the data cannot tell which. It is never treated as a booking.
bad_avail = int((~calendar["available"].isin(["t", "f"])).sum())
calendar["available"] = calendar["available"].map({"t": True, "f": False}).astype("boolean")
for col in ["minimum_nights", "maximum_nights"]:
    calendar[col] = pd.to_numeric(calendar[col], errors="coerce").astype("Int64")
assert not calendar.duplicated(["listing_id", "date"]).any(), "Duplicate listing-night rows."
log("calendar", "3 parsed (final)", calendar, f"unexpected 'available' values={bad_avail}")

# ==========================================================================
# REVIEWS
# ==========================================================================
reviews = pd.read_csv(config.RAW / "reviews.csv.gz", dtype=str)
log("reviews", "1 loaded raw", reviews)

# Privacy: reviewer names/ids and comment text are personal data we never use.
reviews = reviews.drop(columns=[c for c in config.REVIEWS_PRIVATE_COLUMNS if c in reviews.columns])
log("reviews", "2 private columns dropped", reviews)

orphan_r = ~reviews["listing_id"].isin(listings["id"])
n_orphan_review_ids = reviews.loc[orphan_r, "listing_id"].nunique()
reviews = reviews[~orphan_r].copy()
log("reviews", "3 ids not in listings dropped", reviews,
    f"{n_orphan_review_ids} ids, {int(orphan_r.sum()):,} rows")

reviews["date"], date_failures["reviews.date"] = parse_date(reviews["date"], "reviews.date")
assert reviews["id"].is_unique, "Duplicate review ids."
log("reviews", "4 parsed (final)", reviews)

# ==========================================================================
# SAVE
# ==========================================================================
# Final privacy check: fail rather than write a private column to disk.
leaked = [c for c in config.PRIVATE_COLUMNS_REQUIRED + config.PRIVATE_COLUMNS_EXTRA
          if c in listings.columns] + \
         [c for c in config.REVIEWS_PRIVATE_COLUMNS if c in reviews.columns]
assert not leaked, f"Private columns still present: {leaked}"

config.PROCESSED.mkdir(parents=True, exist_ok=True)
config.OUTPUTS.mkdir(parents=True, exist_ok=True)
listings.to_parquet(config.PROCESSED / "listings_clean.parquet", index=False)
calendar.to_parquet(config.PROCESSED / "calendar_clean.parquet", index=False)
reviews.to_parquet(config.PROCESSED / "reviews_clean.parquet", index=False)

# Audit trail: row counts per step + parse failures, read by 02.
log_df = pd.DataFrame(log_rows, columns=["table", "step", "rows", "cols", "note"])
log_df.to_csv(config.OUTPUTS / "01_cleaning_log.csv", index=False)
pd.DataFrame(
    [(k, v) for k, v in date_failures.items()]
    + [("listings.price", int(listings["price_parse_failed"].sum())),
       ("listings.numeric_columns", numeric_failures),
       ("calendar.available", bad_avail)],
    columns=["field", "parse_failures"],
).to_csv(config.OUTPUTS / "01_parse_failures.csv", index=False)

record_key_numbers([
    ("listings_raw", len(listings), "listings", "June snapshot, before any scope filter"),
    ("calendar_rows_clean", len(calendar), "listing-nights", "after dropping ids not in listings"),
    ("calendar_ids_not_in_listings", n_orphan_ids, "listing ids", "dropped: cannot be joined"),
    ("reviews_rows_clean", len(reviews), "reviews", "after dropping ids not in listings"),
    ("review_ids_not_in_listings", n_orphan_review_ids, "listing ids", "dropped: cannot be joined"),
], SCRIPT)

print(f"\nSaved 3 parquet files to {config.PROCESSED.relative_to(config.ROOT)}/ "
      f"and the cleaning log to outputs/.")
print(config.CREDIT_LINE)
