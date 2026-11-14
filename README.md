# DataJam 2026: Airbnb Vancouver case

SFU DSSS DataJam 2026. A fictional fund (DDD) invests **$10M CAD** in BC
short-term rental property, live Jan 1, 2027, measured over calendar year 2027.
This repo reproduces every number on our slides: where to buy, how many
properties, what type, the expected 2027 return, its range and the key risks.

Data: Inside Airbnb, Vancouver, 15 June 2026, CC BY 4.0.

## 1. Setup

Python 3.13 (any 3.11+ should work).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Download the data

Raw data is not committed (too large; freely re-downloadable). Everything comes
from Inside Airbnb, <https://insideairbnb.com/get-the-data/>, section
**Vancouver, British Columbia, Canada**. Older snapshots are under
"show archived data" in that section.

We use two snapshots: June 2026 (all four files) and March 2026 (only
`listings.csv.gz` is read). The four files are:

| File | Which one |
|---|---|
| `listings.csv.gz` | the **detailed** listings file (about 90 columns), under "data". NOT the small `listings.csv` summary |
| `calendar.csv.gz` | detailed calendar |
| `reviews.csv.gz` | detailed reviews. NOT the 2-column `reviews.csv` summary |
| `neighbourhoods.geojson` | under "visualisations" |

Direct links follow this pattern (replace `DATE`); if one does not resolve, use
the page above:

```
https://data.insideairbnb.com/canada/bc/vancouver/DATE/data/listings.csv.gz
https://data.insideairbnb.com/canada/bc/vancouver/DATE/data/calendar.csv.gz
https://data.insideairbnb.com/canada/bc/vancouver/DATE/data/reviews.csv.gz
https://data.insideairbnb.com/canada/bc/vancouver/DATE/visualisations/neighbourhoods.geojson
```

Where each snapshot goes:

| Snapshot (`DATE`) | Put the files in | Role |
|---|---|---|
| **2026-06-15** | `data/raw/` (top level) | **Primary.** The snapshot named in the case brief. Scraped during the FIFA World Cup |
| 2026-03-21 | `data/raw/pre_worldcup_2026-03-21/` | Low season, before the World Cup. Only `listings.csv.gz` is needed: price check (step 3) and nightly rate (step 4) on matched listings |

Keep the file names exactly as downloaded. Resulting layout:

```
data/raw/
  listings.csv.gz  calendar.csv.gz  reviews.csv.gz  neighbourhoods.geojson
  pre_worldcup_2026-03-21/
    listings.csv.gz
```

The summary files (`listings.csv`, `reviews.csv`, `neighbourhoods.csv`) are not
used. If you downloaded them, keep them in a `summary_files_unused/` subfolder
so they cannot be loaded by mistake.

Check after downloading: `01_load_clean.py` stops with an error if the top-level
listings file is the summary version or if its earliest `last_scraped` date is
not 2026-06-15 (plus or minus one day).

## 3. Run order

Run from the repo root, in order. Each script prints its row counts and writes
its headline figures to `outputs/key_numbers.csv`.

| Step | Command | Writes | Status |
|---|---|---|---|
| 1 | `python src/01_load_clean.py` | `data/processed/*.parquet`, `outputs/01_cleaning_log.csv`, `outputs/01_parse_failures.csv` | done |
| 2 | `python src/02_data_quality.py` | `outputs/data_quality_report.md`, `outputs/dq_listings_per_neighbourhood.csv` | done |
| 3 | `python src/03_scope_and_price.py` | `data/processed/listings_scope.parquet`, `outputs/03_scope_counts.csv`, `outputs/03_dormant_check.csv`, `outputs/03_world_cup_price_check.csv` | done |
| 4 | `python src/04_nightly_rate.py` | `data/processed/listings_rate.parquet`, `outputs/04_rate_coverage.csv`, `outputs/04_rate_medians.csv`, `outputs/04_rate_ratio.csv` | done |
| 5 | `python src/05_revenue.py` | `data/processed/listings_revenue.parquet`, `outputs/05_revenue_by_neighbourhood.csv` and `.png`, `outputs/05_revenue_by_bedrooms.csv`, `outputs/05_revenue_sensitivity.csv` | done |
| later | returns, portfolio and risk scripts | | not written yet |

Steps 1 and 2 use only the June snapshot. Step 3 also reads `listings.csv.gz` from the March snapshot; step 4 reads the same March file (price columns only) and averages March and June prices. Step 5 multiplies estimated nights booked (from reviews) by that rate; it reads no raw file.

## 4. Repo layout

```
data/raw/            Inside Airbnb downloads (gitignored)
data/external/       small outside datasets, with SOURCES.md
data/processed/      cleaned parquet files (gitignored)
src/config.py        every path, constant and assumption, each with a source
src/common.py        shared helpers (key_numbers.csv writer, markdown tables)
src/0X_*.py          the pipeline, run in order
outputs/             figures, tables, key_numbers.csv, data_quality_report.md
docs/decision_log.md decisions: what, alternatives, evidence, effect on results
```

## 5. Rules we hold the analysis to

- **Privacy.** Host names, host/listing URLs, licence numbers, reviewer names and
  review text are dropped at load and never reach `data/processed/` or `outputs/`.
- **Unavailable is not booked.** A calendar night marked unavailable may be
  booked or blocked by the host. Any share of unavailable nights is an upper
  bound, never an occupancy rate.
- **Estimates are labelled.** Inside Airbnb's `estimated_*_l365d` fields and any
  licence-based rate are estimates; reviews are a proxy for stays.
- **Every slide number traces to code** through `outputs/key_numbers.csv`.
- Every chart and slide carries: `Data: Inside Airbnb, Vancouver, 15 June 2026, CC BY 4.0.`
  (plus the other snapshot's date when a number uses it).
