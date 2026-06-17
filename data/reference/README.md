# Reference (bundled) data

## `land_value_by_district.csv` — STAND-IN, not a live dataset

This is a **transparent stand-in** for a per-district real-estate cost signal, used
as the `real_estate_cost_index` input to the scoring model. It is a small,
hand-maintained table of relative announced-land-value (公告地價) levels for the 12
Taipei City districts, ordered by well-known relative land value (大安/信義/中正 high;
文山/北投/南港 lower). The scoring pipeline min-max scales these values into `[50, 100]`,
so only the **relative ordering and spacing** affect the score, not the absolute numbers.

Why a stand-in: a clean, per-district open dataset of announced land value was not
wired to a working download endpoint at build time (the authoritative parcel-level
公告土地現值 data requires heavy aggregation). Until a live source is added, this
bundled table keeps the full pipeline reproducible end to end.

**Production replacement:** swap this file for a real per-district aggregate of the
government 公告地價/公告土地現值 dataset (same two columns: `district`, `land_value`,
with `district` in the canonical `臺北市{X}區` form). No code change is required —
`scripts/build_station_features.py` reads this path directly.
