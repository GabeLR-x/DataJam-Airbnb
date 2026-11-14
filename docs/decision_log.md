# Decision log

Source for the slide appendix. One entry per choice that could change a result.
Format: **Decided / Alternatives / Evidence / How it changed results**, with
before-vs-after numbers produced by code (script named in each entry).

Entries marked DRAFT were written by Claude Code and still need a team read.

**Pitch shortlist.** The three decisions planned for the pitch are the scope
filter (#4), the nightly-rate rule (#5), and either vacancy-tax treatment (#6)
or property mix, whichever moves the recommendation more. Entries #1-#3 are
appendix backup only: they do not change a result.

---

## #1 Privacy: drop more columns than the minimum list (DRAFT, Nov 11)

**Decided.** At load we drop the seven required columns (`host_name`, `host_url`,
`listing_url`, `picture_url`, `host_picture_url`, `host_thumbnail_url`,
`license`) plus seven more that our 90-column download contains:
`host_profile_url`, `host_profile_id`, `host_about`, `host_location`, `name`,
`description`, `price_quote_raw`. From reviews we drop `reviewer_id`,
`reviewer_name` and `comments`. `host_id` is kept for counting listings per
operator and is never printed or exported.

**Alternatives.** Drop only the required seven; or keep listing `name` /
`description` for text features.

**Evidence.** The extra columns are links to a person's profile or free text
written by hosts and guests, which can contain names and contact details. No
planned step uses them. `01_load_clean.py` asserts none of them reach disk.

**How it changed results.** No effect on any number. Listings 90 -> 80 columns
at the privacy step; reviews 6 -> 3 columns (`outputs/01_cleaning_log.csv`).

---

## #2 Cleaning adds flags; it removes no listings (DRAFT, Nov 11)

**Decided.** `01_load_clean.py` keeps all 6,509 listings. Room type, mid-term
(`minimum_nights` >= 30), missing price and price outliers become flags
(`is_entire_home`, `is_mid_term`, `price_parse_failed`, plus thresholds in
`config.py`). The only rows removed are calendar and review rows whose listing
id is not in listings.

**Alternatives.** Filter to the STR scope during cleaning.

**Evidence.** Scope is a judgement call that moves results, so it should be made
once, visibly, with counts. Rows without a matching listing have no room type,
area or price and cannot be used in any case.

**How it changed results.** Listings 6,509 -> 6,509. Calendar 2,381,626 ->
2,375,786 rows (16 ids, 5,840 rows dropped). Reviews 323,903 -> 323,898 (3 ids,
5 rows dropped).

---

## #3 Licence flag: classify the text, keep no numbers (DRAFT, Nov 11)

**Decided.** The licence field is free text ("Municipal registration number: ...
Provincial registration number: ..."). We classify the municipal part as
`number` (shaped like a City licence number: two-digit year + 5-6 digits),
`exempt`, `other` or `missing`. `has_licence` = `number`. A separate
`has_provincial_registration` flag covers the BC registry number. The text
itself is then dropped.

**Alternatives.** `has_licence` = field is not empty.

**Evidence.** "Not empty" counts 378 listings that say "Exempt" and 65 with other
text (e.g. "30 Day Minimum") as licensed.

**How it changed results.** Not-empty definition: 5,368 listings (82.5%).
Number-shaped definition: 4,925 (75.7%). Both are estimates of what hosts typed,
not verified against the City register (`outputs/data_quality_report.md`, s.8).

---

## #4 (A) Scope filter: active short-term entire homes (DRAFT, Nov 11)

**Decided.** Comparables = entire home/apt, `minimum_nights` < 30, at least 1
review in the last 12 months. We do NOT add a rule that drops the July 6
"previous scrape" group.

**Alternatives.** (a) Keep private rooms. (b) A stricter activity bar (e.g. 3+ or
6+ reviews). (c) Drop every listing scraped on July 6 as dormant.

**Evidence** (`src/03_scope_and_price.py`, `outputs/03_scope_counts.csv`,
`outputs/03_dormant_check.csv`). DDD buys whole properties, so rooms are not
comparable. Stays of 30+ nights are mid-term rentals. One review is the weakest
evidence that a home was rented at all. On (c): the July 6 group looked dormant
in the quality report, but that was because it is mostly mid-term and
private-room listings. Only 214 of its 2,156 listings are short-term entire
homes, and 85.0% of those pass the activity filter, the same as the June 15-16
groups (85.2%). So there is no evidence to remove the remaining 182 by scrape
date; they are 5.5% of the scope.

**How it changed results.** 6,509 listings -> 5,322 entire homes -> 3,857 with
`minimum_nights` < 30 -> **3,285 in scope** (3,230 with a price). Areas with
fewer than 30 priced in-scope listings: Fairview (19) and Strathcona (14);
South Cambie is at the line (30). Reviews are a proxy for stays, so "active"
means "reviewed", not "booked".

---

## #5 (B) Nightly rate: March + June average, not the June price (DRAFT, Nov 12; numbers from script 04)

**Decided.** The June `price` is not used as a 2027 nightly rate as it stands.
Rule implemented in `src/04_nightly_rate.py`, using two snapshots (March and
June 2026):
- **Base case:** each listing's average of its March and June prices.
  Listings with a June price only: June price x 0.871, the median ratio
  (March+June average / June) on listings that have both, flagged
  `rate_adjusted`.
- **Low scenario:** March level (own March price, else June x 0.741).
- **High scenario:** June price as it is.

Known bias: two dates are not twelve months. March is low season and June is
peak season with some event premium, and each counts equally, so the average
is a midpoint between the two, not a measured year-round rate.

**Alternatives.** (a) Use June prices as they are (now the high scenario).
(b) Bring every price down to the March level (now the low scenario; March is
low season, so it understates a year-round rate). (c) Remove only the "event"
part of the change, about 10 points, read from the gap between June quotes
inside the window (+35.5%) and after it (+25.3%). (d) **Three snapshots (March,
June, September 2026): tested, about 1% difference, dropped.** That version
(git commit 9f2b819) gave a base-case median rate of $354.69 vs $359.71 now,
and the same ratio to June, 0.871, on the 2,099 listings priced in all three.
September added a third file and cut coverage from 76.4% to 63.9% of in-scope
listings without changing the answer.

**Evidence** (`outputs/03_world_cup_price_check.csv`). Same listing ids in the
Mar 21 and June snapshots, both priced, both quotes for stays under 30 nights:
4,983 ids in both -> 4,205 both priced -> **3,005 matched**. Median change per
listing **+34.0%** (middle half of listings: +8.4% to +64.6%; 81.2% of listings
went up). Downtown + West End **+33.3%** (739 listings) vs all other areas
**+34.3%** (2,266): no stadium-area effect. In-scope listings only: +34.9%
(2,509). June quotes dated after the window: +25.3% (402 listings).

**What this does and does not show.** It shows June prices sit about a third
above March on the same homes. It does not show how much of that is the World
Cup: March is low season and June-July is peak season in any year. The equal
rise inside and outside the stadium area, and the +25.3% on quotes dated after
the tournament, both suggest most of it is seasonal or city-wide. The after-window
group is a different, smaller set of listings, so the ~10 point gap is a hint,
not a measurement. Consequence: a March-level rate is probably below the true
year-round average, which is why it is the low scenario and not the base case.

**Evidence from script 04** (`outputs/04_rate_coverage.csv`,
`04_rate_medians.csv`, `04_rate_ratio.csv`). Only quotes for stays under 30
nights count as usable. Of the 3,285 in-scope listings: **2,509 (76.4%) have a
usable price in both March and June**; 712 (21.7%) in June only; 64 (1.9%)
have no usable June price and get no rate. On the 2,509: median price $303
(March), $417.50 (June); March+June average $368.50. Ratio average / June:
**0.871** overall (middle half of listings 0.803 to 0.957); Downtown + West End
0.875 (670 listings) vs all other areas 0.869 (1,839). The stadium area is not
lower, so one citywide ratio is used. Areas with under 30 listings priced in
both (medians not reliable): Shaughnessy 25, South Cambie 25, Fairview 16,
Strathcona 12.

**Limits.** 712 of the 3,221 rated listings (about a fifth) carry a scaled June
price, not their own two prices. The ratio varies between listings, so it is a
typical value, not a rule each one follows. Each price is one quote on one
date, so day-of-week and length-of-stay differences between quotes are not
controlled. These are asking prices, not prices paid.

**How it changed results.** Median nightly rate across all in-scope listings
with a rate (3,221): **$408 (June as it is) -> $359.71 (base case)**; low
scenario $297. Revenue built on the June price as it is would be higher by the
same proportion as the rate. Slides using these numbers must carry: "Data:
Inside Airbnb, Vancouver, 15 June 2026 and 21 March 2026, CC BY 4.0."

---

## #6 Vacancy taxes apply in the base case (DRAFT, Nov 12; numbers pending, script 06)

**Decided.** Base case charges Vancouver's Empty Homes Tax (3% of value per
year) and BC's Speculation and Vacancy Tax (1%, the rate for Canadian owners
from 2026): about 4% of property value per year. `VACANCY_TAXES_APPLY = True`.

**Alternatives.** (a) Taxes excluded (run as a sensitivity). (b) A hybrid
strategy: mid-term stays of 30+ nights in low season and short-term in peak
season, to meet the taxes' occupancy test (rented 30+ consecutive days for 6+
months of the year).

**Evidence.** The brief waives only the principal-residence requirement and
says all other rules still apply; these are separate taxes. A short-term rental
that is not owner-occupied does not count as occupied under either tax. DDD is
assumed Canadian-owned, so the 1% SVT rate, not the foreign rate. Organizers
have not yet answered.

**How it changed results.** Yield with vs without the taxes: numbers pending
(script 06). At about 4% of value per year this can flip the recommendation.

---

## #7 Budget: $10M covers all-in acquisition, no leverage (DRAFT, Nov 12; numbers pending, script 06)

**Decided.** The $10M pays for purchase price + Property Transfer Tax +
furnishing/setup. No borrowing. Operating costs are paid from 2027 revenue.

**Alternatives.** (a) $10M covers purchase price only. (b) Levered purchase.

**Evidence.** The brief gives no financing terms. Unlevered keeps property types
comparable and matches the return metric (net operating income / all-in cost).

**How it changed results.** Number of properties bought under all-in vs
price-only budgeting: numbers pending (script 06).

---

## #8 Purchase-price source: GVR benchmark by area and type (DRAFT, Nov 12; numbers pending, script 06)

**Decided.** Purchase price = Greater Vancouver Realtors benchmark price,
October 2026, by area (Vancouver East / Vancouver West) x property type
(`data/external/gvr_benchmark_prices.csv`).

**Alternatives.** (a) One citywide average price. (b) Assessed values from the
City's property tax report (see #9).

**Evidence.** West vs East gap by type: apartment $751,400 vs $635,100;
townhouse $1,285,000 vs $1,055,800; detached $2,899,700 vs $1,610,700. A single
citywide price would hide these gaps.

**Limits.** A benchmark is the price of a typical home, not of the homes that
are run as short-term rentals. Prices are at area level only (East / West), not
by neighbourhood.

**How it changed results.** Numbers pending (script 06).

---

## #9 Property tax report join skipped (DRAFT, Nov 12; numbers pending, script 06)

**Decided.** We do not join the City's property tax report. For property-tax
and vacancy-tax calculations, assessed value is assumed equal to the GVR
benchmark price (#8).

**Alternatives.** Join assessed values by neighbourhood and property type.

**Evidence.** The report's neighbourhood codes do not match ours, and "a join
you cannot defend is worse than no join" (brief s.4).

**Direction of bias.** 2026 assessments reflect mid-2025 values, before the
roughly 4-9% price fall, so real assessed values, and the taxes based on them,
may be higher than we assume.

**How it changed results.** Numbers pending (script 06).

---

## #10 Organizer rulings used (DRAFT, Nov 12)

**Decided.** We rely on two rulings from the DataJam help channel.
- **Other Inside Airbnb snapshots are allowed if credited (Nov 10):** "Any data
  gathered from the sources we have provided is considered valid." We use the
  March 2026 snapshot for the nightly rate (#5) and name both snapshot dates
  in the credit line of any slide that uses it. The September 2026 snapshot
  was tested and dropped (#5, alternative d).
- **Strathcona / Downtown Eastside handling is our choice (Nov 8).** Inside
  Airbnb splits the City's Strathcona into "Strathcona" and "Downtown
  Eastside". How we map them is an open item below.

**Alternatives.** June snapshot only.

**How it changed results.** Makes #5 possible; effect reported there.

---

## #11 Revenue method: Inside Airbnb's review-based nights x our nightly rate (DRAFT, Nov 13; numbers from script 05)

**Decided.** Estimated annual revenue per listing = estimated nights booked x
our base nightly rate (#5). Nights booked are Inside Airbnb's
`estimated_occupancy_l365d`, which we first rebuilt ourselves: reviews in the
last 12 months / 50% review rate x 3 nights per stay (or the listing's minimum
stay if longer), capped at 255 nights (70% of a year). Our formula matches the
field on 100.0% of the 3,285 in-scope listings, and it is the method Inside
Airbnb publishes on its "Data Assumptions" page. The three constants are in
`config.py`. This is an estimate: reviews are a proxy for stays, and the rate
is an asking price, not a price paid.

**Alternatives.**
- (a) Use Inside Airbnb's `estimated_revenue_l365d` as it is. Rejected: it is
  the same nights x the June price, quoted in peak season during the World Cup.
- (b) Count unavailable calendar nights as booked. Rejected: an unavailable
  night may be blocked by the host; this gives an upper bound at best.
- (c) Bound nights by 365 minus `availability_365`. Not done: that field looks
  365 days forward, reviews look 365 days back, so it does not bound past
  bookings.
- (d) A different review rate. Kept as a sensitivity: 72% and 30.5%, the two
  published figures Inside Airbnb's 50% sits between.

**Evidence** (`src/05_revenue.py`, `outputs/05_revenue_sensitivity.csv`).
- Median estimated nights: 102 a year in the base case; 14.6% of listings are
  at the 255-night cap.
- Check against Inside Airbnb: on 3,221 listings the median of ours / theirs
  is 0.871 (p25 0.825, p75 0.928). That equals the rate ratio in #5, so the
  whole gap is our price adjustment.
- Sensitivity of the median estimated revenue (base $38,104):

| Case | Median estimated revenue | vs base |
|---|---|---|
| Nightly rate low (March level) | $32,017 | -16.0% |
| Nightly rate high (June as it is) | $42,547 | +11.7% |
| Review rate 72% (median 71 nights) | $26,750 | -29.8% |
| Review rate 30.5% (median 167 nights) | $56,084 | +47.2% |

**How it changed results.** Median estimated revenue is $38,104 per listing
(p25 $15,140, p75 $65,538) on 3,221 listings; 64 in-scope listings have no
rate and no estimate. Using Inside Airbnb's figure unchanged would be about
13% higher. The review rate is the largest single uncertainty, larger than the
nightly rate. Known limits: nights are from the 12 months before the scrape
and stand in for 2027; a listing open for less than 12 months is understated.

---

## #12 Operating model: hybrid over full-time short stays (DRAFT, Nov 14; numbers from script 06, first pass)

**Decided.** Lead with the negative result: after vacancy taxes, full-time short-term rental does not beat
long-term rental in the City of Vancouver. The recommended structure is the hybrid (short stays May-Oct,
30+ night stays Nov-Apr), which meets the occupancy test of both vacancy taxes (#6).

**Alternatives.** (a) Full-time short stays, taxes charged. (b) Full-time short stays, taxes assumed away.
(c) Plain long-term rental at CMHC rents.

**Evidence** (`src/06_returns.py`, `outputs/06_three_models_by_segment.csv`). Net yield on all-in cost,
median comparable listing: full-time with taxes is negative in all six segments (-1.4% to -4.0%); hybrid
+0.5% to +2.5%; long-term +0.9% to +2.5%. At the median the hybrid only matches long-term rental; at the
top-quartile listing it is ahead (West 2-bed apartment 4.5% vs 2.5%). 62.9% of reviews fall in May-Oct.
Monthly-stay listings are priced below CMHC rents and only about a third had a review in the last 12
months, so winter demand is the weakest assumption.

**Tested and did not hold.** Multi-listing hosts earn less, not more, than single-listing hosts (median
about $28,500 vs $42,200). No first-year penalty for new listings: year-1 / year-2 reviews = 1.17 on 430
listings (survivors only), so no ramp-up cut is applied.

**How it changed results.** West 1-bed apartment: -2.1% (full-time, taxes) -> +1.6% (hybrid). Portfolio of
12-14 apartments: hybrid P10-P90 about 1% to 5% of $10M per year; 3-5 houses about 0.2% to 1.9%.

**Limits.** Cost inputs in script 06 marked "assumption" are not yet sourced. One GVR apartment benchmark
is used for 1- and 2-bed units, which flatters 2-bed yields. Neighbourhood -> East/West and property type
-> apartment/detached mappings are in script 06; guest suites and guesthouses (621 listings) are excluded
because DDD cannot buy them separately from the house.

---

## Open items found in data quality (not yet decided)

These came out of `02_data_quality.py` and need a decision before 03.

- **`price` is a quote for one stay, not a yearly rate.** 75.3% of priced
  listings were quoted for a check-in inside the World Cup window, and 23.8% of
  quotes are for 30+ night stays. 336 of the 337 prices under $30/night are 30+
  night quotes.
- (Resolved in #11) `estimated_revenue_l365d` is Inside Airbnb's estimated
  nights x the June `price`, so it inherits the June price level.
- (Resolved in #4) The July 6 "previous scrape" group: no separate removal rule.
- **Small areas:** Fairview (25) and Strathcona (14) have under 30 priced,
  short-term entire homes.
- **Strathcona / Downtown Eastside mapping** to the City's 22 local areas.
- **Neighbourhood -> Vancouver East / West mapping**, needed for the GVR join
  in script 06. Goes in a CSV in `data/external/`.
- **Airbnb `property_type` -> detached / townhouse / apartment mapping**, needed
  for the GVR join in script 06. Goes in a CSV in `data/external/`.
