# Outside data sources

Every file in this folder gets one row. Rule: public, free, no login, no scraping.

| File | What it is | Publisher | URL | Retrieved | Licence | Used in |
|---|---|---|---|---|---|---|
| *(none yet)* | | | | | | |

## gvr_benchmark_prices.csv
- Source: Greater Vancouver REALTORS, "GVR Stats Package October 2026" (free public PDF), MLS Home Price Index benchmark price tables.
- Extracted with `pdftotext -layout` and a regex (Vancouver East, Vancouver West, Greater Vancouver rows only); spot-check against the PDF.
- Granularity: area (Vancouver East / West) x property type. No neighbourhood-level prices in the package.
- The PDF itself is not committed (data/external/*.pdf is gitignored).

## cmhc_rent_{studio,1bed,2bed,3bed}_oct2025.csv
- Source: CMHC Housing Market Information Portal, Vancouver CMA, "Rental Market Statistics Summary by Zone", October 2025, Row / Apartment, one export per bedroom type (free, no login). Staged for all teams in the case brief.
- Exported as CSV from the portal on 2026-11-14; files are unedited (latin-1 encoded, two title rows).
- Used in `src/06_returns.py`: average rent by zone, for the long-term rental comparison. `**` = suppressed by CMHC.
- Zones used: West = West End/Stanley Park, English Bay, Downtown, South Granville/Oak, Kitsilano/Point Grey; East = Mount Pleasant/Renfrew Heights, East Hastings, Southeast Vancouver (simple average; our choice).
