# Decision log

Source for the slide appendix. One entry per choice that could change a result.
Format: **Decided / Alternatives / Evidence / How it changed results**, with
before-vs-after numbers produced by code (script named in each entry).

Entries marked DRAFT were written by Claude Code and still need a team read.

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

## #5 (B) World Cup: June prices are not used unadjusted (DRAFT, Nov 11; rate rule still to be agreed)

**Decided (proposed).** The June `price` is not used as a 2027 nightly rate as
it stands. Proposed base case: bring June prices down to the March level using
the matched-listing change below; show the unadjusted June price only as an
upper sensitivity.

**Alternatives.** (a) Use June prices as they are. (b) Use the March price
directly for matched listings only (loses unmatched listings). (c) Remove only
the "event" part of the change, about 10 points, read from the gap between June
quotes inside the window (+35.5%) and after it (+25.3%).

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
year-round average, so the proposed base case is conservative.

**How it changed results.** Median nightly price on in-scope matched listings:
$417.50 (June, unadjusted) -> $303 (March level). Any revenue built on the
unadjusted June price would be about a third higher. Slides using this must
credit both snapshots: "Data: Inside Airbnb, Vancouver, 15 June 2026 and
21 March 2026, CC BY 4.0."

---

## Open items found in data quality (not yet decided)

These came out of `02_data_quality.py` and need a decision before 03.

- **`price` is a quote for one stay, not a yearly rate.** 75.3% of priced
  listings were quoted for a check-in inside the World Cup window, and 23.8% of
  quotes are for 30+ night stays. 336 of the 337 prices under $30/night are 30+
  night quotes.
- **`estimated_revenue_l365d` is missing for exactly the listings with no
  `price`**, which suggests it is built from `price` and inherits any inflation.
- (Resolved in #4) The July 6 "previous scrape" group: no separate removal rule.
- **Small areas:** Fairview (25) and Strathcona (14) have under 30 priced,
  short-term entire homes.
- **Strathcona / Downtown Eastside mapping** to the City's 22 local areas.
