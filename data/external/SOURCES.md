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
