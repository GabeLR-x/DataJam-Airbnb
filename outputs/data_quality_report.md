# Data quality report: Inside Airbnb Vancouver, June 2026 snapshot

*Data: Inside Airbnb, Vancouver, 15 June 2026, CC BY 4.0.*

Produced by `src/02_data_quality.py` from the cleaned files written by `src/01_load_clean.py`. Nothing here is a model output, and no listing has been filtered out. All figures are aggregates.

## 0. Row counts at every cleaning step

| table | step | rows | cols | note |
|---|---|---|---|---|
| listings | 1 loaded raw | 6509 | 90 |  |
| listings | 2 licence flags derived | 6509 | 94 | has_licence=4,925 |
| listings | 3 private columns dropped | 6509 | 80 |  |
| listings | 4 all-empty columns dropped | 6509 | 68 | 12 columns |
| listings | 5 dates parsed | 6509 | 68 | failures=0 |
| listings | 6 price parsed | 6509 | 71 | price present=5,845 |
| listings | 7 numeric columns converted | 6509 | 71 | failures=0 |
| listings | 8 flags added (final) | 6509 | 73 |  |
| calendar | 1 loaded raw | 2381626 | 5 |  |
| calendar | 2 ids not in listings dropped | 2375786 | 5 | 16 ids, 5,840 rows |
| calendar | 3 parsed (final) | 2375786 | 5 | unexpected 'available' values=0 |
| reviews | 1 loaded raw | 323903 | 6 |  |
| reviews | 2 private columns dropped | 323903 | 3 |  |
| reviews | 3 ids not in listings dropped | 323898 | 3 | 3 ids, 5 rows |
| reviews | 4 parsed (final) | 323898 | 3 |  |

## 1. Missing values in key columns

| column | missing (all) | % of all listings | % of entire homes |
|---|---|---|---|
| price | 664 | 10.2% | 9.9% |
| estimated_revenue_l365d | 664 | 10.2% | 9.9% |
| estimated_occupancy_l365d | 0 | 0.0% | 0.0% |
| number_of_reviews_ltm | 0 | 0.0% | 0.0% |
| first_review | 1136 | 17.5% | 15.5% |
| minimum_nights | 5 | 0.1% | 0.1% |
| room_type | 0 | 0.0% | 0.0% |
| neighbourhood_cleansed | 0 | 0.0% | 0.0% |
| property_type | 0 | 0.0% | 0.0% |
| accommodates | 0 | 0.0% | 0.0% |
| bedrooms | 838 | 12.9% | 3.9% |
| beds | 2197 | 33.8% | 31.3% |
| bathrooms | 2469 | 37.9% | 35.6% |
| bathrooms_text | 3 | 0.0% | 0.0% |
| latitude | 0 | 0.0% | 0.0% |
| longitude | 0 | 0.0% | 0.0% |
| calculated_host_listings_count | 0 | 0.0% | 0.0% |
| has_availability | 30 | 0.5% | 0.5% |
| price_quote_checkin_date | 592 | 9.1% | 8.9% |
| review_scores_rating | 1136 | 17.5% | 15.5% |

Licence text was missing for 1,141 listings (17.5%); see section 8.

Columns that are 100% empty in our download and were removed in 01 (so they cannot be used): `host_since`, `host_response_time`, `host_response_rate`, `host_acceptance_rate`, `host_neighbourhood`, `host_total_listings_count`, `host_verifications`, `neighbourhood`, `neighbourhood_group_cleansed`, `neighborhood_overview`, `calendar_updated`, `instant_bookable`.

**Price missingness is not random.** By scrape date:

| scraped | listings | price_missing | % missing |
|---|---|---|---|
| 2026-06-15 | 1295 | 0 | 0.0% |
| 2026-06-16 | 3058 | 13 | 0.4% |
| 2026-07-06 | 2156 | 651 | 30.2% |

Listings without a price: median reviews in the last 12 months = 0 (with a price: 5); 74.8% of them had no review in the last 12 months (with a price: 27.9%).
`estimated_revenue_l365d` is missing for exactly the same listings as `price` in 100.0% of rows: Inside Airbnb's revenue estimate is built from `price`, so it inherits both its gaps and any event inflation.

## 2. Price: parse failures, what it measures, outliers

- Price text present: 5,845; parsed to a number: 5,845; **parse failures: 0**; missing in the source: 664.
- Parse failures in every parsed field (from 01):

| field | parse_failures |
|---|---|
| listings.last_scraped | 0 |
| listings.calendar_last_scraped | 0 |
| listings.first_review | 0 |
| listings.last_review | 0 |
| listings.price_quote_checkin_date | 0 |
| listings.price_quote_checkout_date | 0 |
| calendar.date | 0 |
| reviews.date | 0 |
| listings.price | 0 |
| listings.numeric_columns | 0 |
| calendar.available | 0 |

**What `price` is.** In this download `price` equals `price_quote_price_per_night`: the per-night price of one quoted stay that starts on `price_quote_checkin_date`. It is not an average rate for the year.

- Quoted check-in date falls inside the World Cup window (2026-06-13 to 2026-07-07) for **4,399 of 5,845 priced listings (75.3%)**.
- Quoted stay length: median 2 nights; 1,880 quotes are for 1 night; **1,389 (23.8%) are for stays of 30+ nights** (a monthly rate spread per night, not a short-term nightly price).

Median price by quote date, entire homes with `minimum_nights` < 30 (descriptive, NOT a causal premium: listings quoted outside the window are a different mix of listings):

| quote | listings | median_price |
|---|---|---|
| inside World Cup window | 3327 | $423 |
| outside window | 454 | $385 |

**Distribution and outliers** (all priced listings, nothing removed):

| percentile | price |
|---|---|
| p1 | $15 |
| p5 | $28 |
| p25 | $156 |
| p50 | $318 |
| p75 | $497 |
| p95 | $999 |
| p99 | $2,042 |

- Min $6.17, max $91,294.
- Below $30/night: 337 listings, of which 336 are 30+ night quotes.
- Above $2,000/night: 62 listings.
- Thresholds are flags set in `config.py` (assumption), not filters.

## 3. `minimum_nights` distribution

| minimum_nights | all listings | entire homes | % of all |
|---|---|---|---|
| 1 | 2777 | 2239 | 42.7% |
| 2 | 1354 | 1216 | 20.8% |
| 3 | 273 | 248 | 4.2% |
| 4-6 | 119 | 109 | 1.8% |
| 7-29 | 52 | 45 | 0.8% |
| 30 | 48 | 44 | 0.7% |
| 31-89 | 1 | 1 | 0.0% |
| 90+ | 1880 | 1415 | 28.9% |

- Missing `minimum_nights`: 5 listings.
- **1,929 listings (29.6%) have a minimum of 30+ nights**: mid-term rentals, not STR comparables (candidates for mid-term price comparables in the hybrid test).
- Entire homes with `minimum_nights` < 30: **3,857** (before any activity filter).

## 4. Room types

| room_type | listings | % of all | of which min_nights >= 30 |
|---|---|---|---|
| Entire home/apt | 5322 | 81.8% | 1460 |
| Private room | 1168 | 17.9% | 464 |
| Shared room | 16 | 0.2% | 2 |
| Hotel room | 3 | 0.0% | 3 |

## 5. Listings per neighbourhood

| neighbourhood | all_listings | entire_home | entire_home_short_term | ...with a price | small_n_flag |
|---|---|---|---|---|---|
| Downtown | 1534 | 1422 | 910 | 887 |  |
| Kitsilano | 440 | 386 | 269 | 263 |  |
| Downtown Eastside | 423 | 398 | 336 | 335 |  |
| Kensington-Cedar Cottage | 410 | 329 | 275 | 267 |  |
| Mount Pleasant | 394 | 298 | 166 | 162 |  |
| Hastings-Sunrise | 345 | 251 | 214 | 209 |  |
| Dunbar Southlands | 308 | 181 | 160 | 158 |  |
| West End | 295 | 263 | 100 | 100 |  |
| Riley Park | 290 | 245 | 202 | 199 |  |
| Renfrew-Collingwood | 269 | 209 | 185 | 182 |  |
| Grandview-Woodland | 253 | 219 | 163 | 157 |  |
| Sunset | 228 | 179 | 156 | 154 |  |
| Marpole | 193 | 126 | 93 | 91 |  |
| Victoria-Fraserview | 190 | 152 | 141 | 138 |  |
| Arbutus Ridge | 149 | 97 | 81 | 79 |  |
| West Point Grey | 145 | 93 | 81 | 79 |  |
| Fairview | 136 | 128 | 27 | 25 | SMALL |
| Killarney | 118 | 95 | 84 | 84 |  |
| Oakridge | 115 | 69 | 61 | 59 |  |
| Shaughnessy | 95 | 57 | 47 | 45 |  |
| Kerrisdale | 93 | 57 | 55 | 54 |  |
| South Cambie | 62 | 46 | 36 | 35 |  |
| Strathcona | 24 | 22 | 15 | 14 | SMALL |

- 23 neighbourhood names (the City has 22 local areas; Inside Airbnb adds "Downtown Eastside"). Any join to City open data needs an explicit mapping.
- Top 3 areas hold 36.8% of all listings.
- **2 areas have fewer than 30 priced, short-term entire homes** (flagged SMALL): too few to rank on a median without a wide range.
- "Entire home, short-term" = `room_type` entire home/apt and `minimum_nights` < 30; no activity filter applied yet.

## 6. `last_scraped` split

| scraped | source | listings | % of all | price_missing | no_reviews_ltm | median_reviews_ltm | median_availability_365 |
|---|---|---|---|---|---|---|---|
| 2026-06-15 | city scrape | 1295 | 19.9% | 0.0% | 17.3% | 10.0 | 157.0 |
| 2026-06-16 | city scrape | 3058 | 47.0% | 0.4% | 15.8% | 12.0 | 140.0 |
| 2026-07-06 | previous scrape | 2156 | 33.1% | 30.2% | 65.9% | 0.0 | 211.0 |

- Every scrape date is inside the World Cup window (2026-06-13 to 2026-07-07).
- The July 6 group is 100% `source = previous scrape`: listings carried over from an earlier scrape and re-visited three weeks later. Their `*_l365d` / `*_ltm` windows and calendars start ~3 weeks later than the rest.
- Calendar dates run 2026-06-15 to 2027-07-05. Dates covered by every listing: **2026-07-06 to 2027-06-14** (344 days). Compare listings on calendar date, not on "days ahead".
- Calendar coverage of 2027: through 2027-07-05 only, so the calendar cannot describe the second half of DDD's measured year.

## 7. Calendar: share of nights unavailable (NOT occupancy)

> **This is not an occupancy rate.** An unavailable night is either booked or blocked by the host; the data does not say which. Read every figure in this section as an **upper bound** on booked nights. The monthly table below shows why: the unavailable share is highest 9-12 months after the scrape, when very few guests have booked yet, so much of it must be hosts who have not opened their calendar that far ahead.

- Listing-nights: 2,375,786 across 6,509 listings.
- Unavailable: 1,253,796 nights = **52.8%** (upper bound on booked share, not occupancy).
- Listings unavailable on **every** night for a year: 415 (6.4%). These are almost certainly blocked or dormant, not fully booked, which shows why unavailable is not the same as booked.
- Listings available on every night: 231 (3.5%).
- Excluding the always-unavailable listings, the unavailable share is 49.6% (still an upper bound).

Unavailable share by month, restricted to dates every listing covers (first and last months are partial):

| month | listing-nights | unavailable share (upper bound) |
|---|---|---|
| 2026-07 | 169234 | 57.0% |
| 2026-08 | 201779 | 52.7% |
| 2026-09 | 195270 | 47.8% |
| 2026-10 | 201779 | 45.5% |
| 2026-11 | 195270 | 42.9% |
| 2026-12 | 201779 | 47.0% |
| 2027-01 | 201779 | 51.8% |
| 2027-02 | 182252 | 50.9% |
| 2027-03 | 201779 | 56.3% |
| 2027-04 | 195270 | 62.1% |
| 2027-05 | 201779 | 62.1% |
| 2027-06 | 91126 | 62.8% |

## 8. Licence field (estimate, aggregates only)

> **Estimate.** This is what hosts typed into the listing page, classified by pattern. It was not checked against the City of Vancouver licence register, a number can be invalid, expired or reused, and a blank field can be a scrape gap rather than an unlicensed listing. Licence numbers themselves were discarded in 01.

| municipal licence field | meaning | all listings | % of all | entire home, short-term | % of those |
|---|---|---|---|---|---|
| number | text shaped like a City licence number | 4925 | 75.7% | 3670 | 95.2% |
| exempt | host wrote "Exempt" | 378 | 5.8% | 170 | 4.4% |
| other | other text (e.g. "30 Day Minimum") | 65 | 1.0% | 14 | 0.4% |
| missing | field empty | 1141 | 17.5% | 3 | 0.1% |

- Licence field filled (any text): 5,368 = **82.5%** of listings (estimate).
- `has_licence` (number-shaped text): 4,925 = **75.7%** (estimate).
- Provincial registration number shown: 4,309 = 66.2% (estimate).
- Among mid-term listings (`minimum_nights` >= 30), which do not need an STR licence: field empty for 58.8%, vs 0.1% for short-term entire homes.
- Field empty for 36.6% of listings with no reviews vs 13.5% of listings with reviews.

## 9. Join integrity: ids not in listings

- Calendar ids not in listings: **16 ids, 5,840 rows** dropped in 01 (no room type, area or price to join to).
- Review listing ids not in listings: 3 ids, 5 rows dropped in 01.
- Listings with no calendar rows: 0.
- Listings with no review rows: 1,136 (listings reporting `number_of_reviews` = 0: 1,136).
- Nights per listing in calendar: {365: 6508, 366: 1} (nights: listings).
- Reviews run 2010-02-17 to 2026-07-05. Reviews are a proxy for stays, not a count of them.

---
*Data: Inside Airbnb, Vancouver, 15 June 2026, CC BY 4.0.*
