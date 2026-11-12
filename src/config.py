"""
config.py: every path, constant and assumption used by the pipeline lives here.

Why one file: every number on a slide has to trace back to code, and every
assumption has to be defensible in Q&A. If an assumption is not in this file
(with a source or an explicit "assumption" label), it should not be in the model.

Only the settings needed for loading / data quality are filled in so far.
Cost and return assumptions get added when we reach 03-06, each with a source.
"""
from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"               # primary (June) snapshot sits at the top level
PROCESSED = ROOT / "data" / "processed"   # gitignored parquet outputs
EXTERNAL = ROOT / "data" / "external"     # small outside datasets + SOURCES.md
OUTPUTS = ROOT / "outputs"
KEY_NUMBERS = OUTPUTS / "key_numbers.csv"

# Other snapshots (NOT loaded by 01/02; used later for the World Cup test and
# for validation).
RAW_PRE_WORLDCUP = RAW / "pre_worldcup_2026-03-21"
RAW_VALIDATION = RAW / "validation_2026-09-17"

# --------------------------------------------------------------------------
# Credit line: must appear on every chart, slide and report.
# If a number uses another snapshot, name that snapshot's date as well
# (organizer ruling, Nov 10).
# --------------------------------------------------------------------------
CREDIT_LINE = "Data: Inside Airbnb, Vancouver, 15 June 2026, CC BY 4.0."

# --------------------------------------------------------------------------
# Snapshot facts
# --------------------------------------------------------------------------
# The brief calls this the "15 June 2026" snapshot. 01_load_clean.py checks that
# the earliest last_scraped date is within +/- 1 day of this.
SNAPSHOT_DATE = "2026-06-15"

# FIFA World Cup matches in Vancouver. The whole scrape window falls inside it,
# so listing prices are likely event-inflated (tested later across snapshots).
WORLD_CUP_START = "2026-06-13"
WORLD_CUP_END = "2026-07-07"

# All three files in OUR download use ISO dates. We still parse with an explicit
# format so that a different format fails loudly (counted) instead of being
# silently guessed.
DATE_FORMAT = "%Y-%m-%d"

# --------------------------------------------------------------------------
# Privacy (CLAUDE.md rule 1)
# --------------------------------------------------------------------------
# Required drops: anything that names or links to a host or a listing.
# `license` is dropped only AFTER the has-licence flags are derived.
PRIVATE_COLUMNS_REQUIRED = [
    "host_name", "host_url", "listing_url", "picture_url",
    "host_picture_url", "host_thumbnail_url", "license",
]
# Extra drops (our choice, decision log #1): present in our 90-column download
# but not in the required list. Same reasoning: they identify a person or a
# listing, or are free text that can contain names / contact details, and the
# analysis does not need them.
PRIVATE_COLUMNS_EXTRA = [
    "host_profile_url", "host_profile_id",   # link / id of the host's profile page
    "host_about", "host_location",           # free text written by the host
    "name", "description",                   # listing free text
    "price_quote_raw",                       # raw JSON blob; the parsed quote fields are kept
]
# Reviews: reviewer identity and comment text are personal data we never use.
# We only need "a review happened on this date for this listing".
REVIEWS_PRIVATE_COLUMNS = ["reviewer_id", "reviewer_name", "comments"]

# host_id is KEPT (needed to count listings per operator) but must never be
# printed, plotted or exported as a label.

# --------------------------------------------------------------------------
# Thresholds used for flags in the data-quality report (not filters)
# --------------------------------------------------------------------------
# Listings with minimum_nights >= 30 are mid-term rentals under BC rules
# (a stay of 30+ nights is not a short-term rental), so not STR comparables.
MID_TERM_MIN_NIGHTS = 30
# An area with fewer listings than this gets flagged: medians from so few
# listings are too noisy to rank areas on. Assumption (rule of thumb).
SMALL_N_THRESHOLD = 30
# Price sanity bounds for FLAGGING only (nothing is removed in 01/02).
# Assumption: under $30/night or over $2,000/night is implausible for a normal
# Vancouver STR and deserves a manual look before it enters a median.
PRICE_FLAG_LOW = 30
PRICE_FLAG_HIGH = 2000

# --------------------------------------------------------------------------
# Scope filter and World Cup price check (03_scope_and_price.py)
# --------------------------------------------------------------------------
# "Active" = at least this many reviews in the last 12 months. Reviews are a
# proxy for stays, so 1 is the weakest evidence that anyone stayed at all.
# Assumption; decision log A.
MIN_REVIEWS_LTM = 1
# Areas where World Cup demand should be strongest (BC Place is Downtown; the
# West End is the adjacent hotel/visitor district). Assumption, used only to
# split the price check into "near the stadium" vs "everywhere else".
WORLD_CUP_CORE_AREAS = ["Downtown", "West End"]
# Any number using the March file must carry this credit (organizer ruling).
CREDIT_LINE_WITH_MARCH = ("Data: Inside Airbnb, Vancouver, 15 June 2026 and "
                          "21 March 2026, CC BY 4.0.")
