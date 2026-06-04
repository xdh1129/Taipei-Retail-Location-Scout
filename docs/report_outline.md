# Product Brief Outline

This outline can be used for a product brief, technical overview, investor-style memo, or demo handout.

## Cover

- Project title: Taipei Retail Location Scout
- Team or author name
- Repository URL
- Live demo URL, if deployed

## 1. Target Customer

Small coffee, beverage, and light-meal chains in Taipei that need a fast first-pass tool for ranking possible expansion areas before paying for site visits, brokers, or consultants.

## 2. Evidence of Demand and Willingness to Pay

Use public-data validation. The detailed evidence is prepared in `docs/demand_evidence.md`.

- Public restaurant/business registrations show dense competition and active market entry.
- Existing location intelligence products demonstrate paid demand, including one-time site reports and monthly subscription plans.
- Store opening and lease decisions are costly, so a low-cost screening report can save time and reduce bad-location risk.
- The proposed pricing is NTD 990 per report or NTD 2,990 per month for repeated searches.
- The six-area manual screening proxy is 150 minutes; the dashboard review and CSV export proxy is 3 minutes.

## 3. Business Model

Start with report-based pricing for small operators and a monthly SaaS plan for small chains or franchise consultants.

- One-time comparison report: NTD 990.
- Monthly dashboard plan: NTD 2,990.
- Upsell path: custom reports for franchise consultants or multi-location chains.

## 4. Technical System Design

Describe ingestion, storage, processing, scoring, and dashboard delivery. Include the architecture diagram from `docs/architecture.md`.

## 5. Implementation

Explain the current implementation:

- Station-level feature table.
- Transparent scoring formula.
- Streamlit dashboard.
- Reproducible sample pipeline.
- Demand evidence document and public-source citations.

## 6. Go-to-Market Difficulties

- Trust in open-data-derived scores.
- Data freshness and address geocoding quality.
- Competition from larger location intelligence vendors.
- Limits of using transaction price as a rent proxy.

## 7. Scalability and Cost

Explain how the system can scale from local CSV processing to scheduled ingestion, object storage, DuckDB/Spark batch processing, and an API/dashboard layer.
