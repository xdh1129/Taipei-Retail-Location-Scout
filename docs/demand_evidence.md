# Demand Evidence and Willingness to Pay

## Validation Approach

Interviews were not feasible within the project timeline, so this project uses a public-data validation approach. The goal is not to prove exact revenue lift. The goal is to show that the customer problem is real, economically meaningful, and already served by paid location-intelligence products.

The evidence chain is:

1. Retail location selection is a high-cost decision for restaurants and beverage shops.
2. Existing vendors sell location intelligence, site scoring, competitor analysis, and site reports.
3. Taipei food-service competition is dense enough that manual screening is time-consuming.
4. The current system reduces the first-pass screening workflow from manual lookup to a ranked dashboard.
5. The proposed price is small relative to store-opening costs and comparable to lightweight location-analysis products.

## Target Customer

The initial customer is a small coffee, beverage, or light-meal chain evaluating Taipei MRT-adjacent expansion areas. The primary user is an owner, franchise operator, expansion manager, or consultant who needs to shortlist locations before broker visits, lease negotiations, or deeper due diligence.

The wedge is intentionally narrow:

- Geography: Taipei MRT-adjacent trade areas.
- Business type: coffee, beverage, and light-meal stores.
- Use case: first-pass site screening, not revenue prediction.

## Evidence 1: The Decision Is Expensive

Restaurant and cafe location decisions have high downside risk because opening a store requires large upfront investment and recurring fixed costs. Taiwan-focused cost references show that even modest restaurants or cafes require substantial capital:

- OrderEase's Taiwan restaurant cost estimator shows an example total initial investment of NTD 2,993,000 and estimated monthly fixed spending of NTD 313,500 for its default scenario. It also breaks costs into renovation, kitchen equipment, deposits and first-month rent, labor, marketing, and six months of operating capital. Source: [OrderEase restaurant startup cost estimator](https://orderease.com.tw/tools/restaurant-startup-cost-estimator).
- Falison's 2026 Taiwan restaurant cost guide states that restaurant opening costs can range from NTD 1.5 million to NTD 15 million, with monthly fixed spending from NTD 350,000 to NTD 1.5 million, and argues that Taipei rent differences strongly affect the cost structure. Source: [Falison restaurant cost guide](https://falison.com/open/restaurant/restaurant-cost).

Implication: a low-cost screening report or SaaS dashboard does not need to replace a professional consultant. It only needs to reduce the risk of wasting site visits or signing a poor lease.

## Evidence 2: Paid Products Already Exist

The market already contains paid products that look similar to this product's value proposition:

| Product | Relevant Signal | Pricing Signal |
| --- | --- | --- |
| PlacePilot | Site intelligence reports include competitor analysis, heat maps, strategic recommendations, risk factors, and site-visit checklists. | Starting at USD 49 per report; comparing 2-3 locations starts at USD 79. Source: [PlacePilot pricing](https://placepilot.ai/pricing). |
| Locus | Location scoring uses demographics, competition, foot traffic, accessibility, and recommendations for entrepreneurs, CRE advisors, and multi-site retail. | Explore plan GBP 39/month, Research plan GBP 79/month, Monitor plan GBP 59/month. Source: [Locus pricing](https://www.locusintel.io/). |
| Placer.ai | Enterprise location analytics for retail, restaurants, CRE, and civic users; supports trade-area analysis, competitive tracking, API, and data feeds. | Enterprise-style product; public page emphasizes retail and restaurant expansion use cases. Source: [Placer.ai](https://www.placer.ai/). |

Implication: customers already pay for location intelligence. A Taiwan-focused, open-data-first version can start below enterprise pricing and target small operators.

## Evidence 3: Public Data Shows Dense Competition

This project streamed the official restaurant business registration dataset from data.gov.tw and counted active restaurant businesses in the configured demo districts. The full raw file is not stored because of local disk limits; the reproducible derived summary is stored in `data/processed/competitor_counts_by_district.csv`, with source details in `data/processed/competitor_summary_manifest.json`.

| District | Active Restaurant Registrations |
| --- | ---: |
| Taipei City Zhongshan District | 964 |
| Taipei City Daan District | 742 |
| Taipei City Zhongzheng District | 411 |
| Taipei City Shilin District | 365 |

Across the four configured districts, the system observes 2,482 active restaurant registrations. In the six-station demo table, station-level competitor counts average 550.7 because multiple stations can share the same district-level competitor proxy.

Implication: the target customer faces a crowded market. A tool that combines demand proxies and competition proxies has a concrete decision context.

## Evidence 4: The System Produces Actionable Screening

The dashboard ranks six MRT-adjacent trade areas with a risk-adjusted economic opportunity model:

| Rank | Station | Economic Opportunity Index | Feasibility Ratio | Break-even Capture Rate | Key Reason |
| ---: | --- | ---: | ---: | ---: | --- |
| 1 | Jiantan | 100.00 | 1.35x | 29.68% | Clears cost proxy under current assumptions; low break-even capture requirement; large accessible demand base |
| 2 | Taipei Main Station | 89.05 | 0.89x | 41.63% | Near break-even under conservative assumptions; large accessible demand base |
| 3 | Guting | 78.28 | 0.78x | 47.36% | Moderate feasibility with execution sensitivity |
| 4 | Technology Building | 69.09 | 0.69x | 34.57% | Moderate feasibility; low break-even capture requirement; large accessible demand base |
| 5 | Gongguan | 62.72 | 0.63x | 59.11% | Needs stronger capture, ticket size, or rent assumptions |
| 6 | Zhongshan | 50.69 | 0.51x | 37.74% | Large accessible demand base, but high competition pressure |

The ranking is explainable without implying that lower-ranked trade areas are poor markets. Taipei Main Station has the strongest footfall and remains near break-even, but the model penalizes its high cost proxy and competition pressure. Jiantan ranks first because its demand, competition, and cost proxies produce the strongest feasibility ratio under the current transparent assumptions.

## Evidence 5: Time Saved

Manual first-pass screening requires the user to:

1. Look up MRT foot-traffic data.
2. Look up population by district or village.
3. Estimate restaurant competition.
4. Compare cost proxies.
5. Normalize metrics across candidates.
6. Write a ranked shortlist.

For a six-location comparison, a conservative manual estimate is 25 minutes per candidate, or 150 minutes total. The dashboard produces a ranked table, score explanation, selected-area details, and CSV export in about 3 minutes after the pipeline is run.

| Workflow | Six-Area Screening Time |
| --- | ---: |
| Manual lookup and spreadsheet scoring | 150 minutes |
| Dashboard review and CSV export | 3 minutes |
| Estimated time saved | 147 minutes |

This is an estimated workflow comparison, not a user study. It should be presented as a public-data-based productivity proxy.

## Willingness-to-Pay Estimate

The proposed initial pricing is:

- NTD 990 per one-time location comparison report.
- NTD 2,990 per month for repeated screening and CSV exports.

Rationale:

- NTD 990 is far below the cost of a bad lease decision and below the monthly fixed costs of opening a restaurant.
- NTD 2,990/month is positioned for small operators and consultants who screen multiple areas.
- The pricing sits below or near lightweight international tools after currency conversion, while staying accessible for Taiwan small businesses.

This pricing should be framed as a hypothesis validated by competitor pricing and cost avoidance, not as proven willingness to pay from interviews.

## Limitations

- No interviews were conducted.
- Competition is counted at district level, not exact walking radius.
- Real-estate cost is a district-level proxy, not actual rent.
- The dashboard is a first-pass screening tool, not a revenue forecast.
- The output should guide where to investigate next, not replace broker visits, lease negotiation, or on-site observation.

## Report-Ready Claim

The demand evidence supports a defensible product wedge: small retail operators face expensive and uncertain site-selection decisions; paid location-intelligence products already exist; Taipei public data shows dense food-service competition; and the implemented dashboard turns fragmented open data into a ranked, explainable economic-opportunity shortlist. The product can be monetized as a low-cost report or monthly dashboard because the price is small relative to opening costs and because it saves manual research time during early site screening.
