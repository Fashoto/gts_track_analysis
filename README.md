# GPS Track Analysis — IBRA II

Analysis pipeline for GPS tracking data collected during the IBRA II polio SIA
campaign (Data and GIS Analytics, Data Informatics Department, eHealth Africa).

Raw exports are dropped as `Tracks_0.csv` … `Tracks_7.csv` (15 columns:
`Organization, Field Activity, Tracking Round, Username, Team Code, IMEI, Valid,
GPS Status, GPS Timestamp (UTC), Phone Timestamp (UTC), Lat, Lon, Accuracy m,
Speed mps, Track ID`). These files, the merged/cleaned CSV, the generated
charts, and the final `.pptx` are **not** tracked in this repo (see
`.gitignore`) — only the pipeline scripts are.

## Pipeline

Run in order, from a folder containing the raw `Tracks_*.csv` files:

1. **Merge + repair.** Concatenate the raw files and fix a known defect where
   unescaped commas inside the `Team Code` field split some rows into 16–17
   CSV columns instead of 15 (rejoined back into the Team Code position, no
   rows dropped). Produces `Tracks_merged_clean.csv`.

2. **`analyze.py`** — loads the cleaned CSV, resolves each track's State/LGA/
   Ward via an exact point-in-polygon join against an `admin_boundary.sqlite`
   ward-boundary layer (SpatiaLite, EPSG:4326), then falls back to a team-code
   prefix lookup (e.g. `ZAM` → Zamfara, `KAN` → Kano) for any track that
   geometrically lands outside the 15 campaign states — recovering genuine
   border-area fieldwork instead of writing it off as GPS drift. Computes the
   full analytics suite: daily volume, state ranking, day-one launch pattern,
   days-worked continuity, effort distribution, team-code integrity (missing/
   malformed/duplicated/cross-state codes), device-to-code reconciliation
   against the deployed-device roster, day-to-day churn, hour-of-day pattern,
   and data-quality checks (clock mismatch, implausible speed, poor accuracy).
   Saves results to a pickle for the next two scripts.

3. **`make_charts.py`** — renders the chart set (daily trend, state ranking,
   day-one signal, continuity, effort distribution, teams-per-day, hourly
   pattern, QA overview) as PNGs in `charts/`, styled in eHA brand colors
   (`#0090FC` blue / `#E2EE64` green).

4. **`build_pptx.py`** — assembles the final report from the eHA General
   Slide Template, populating title/section/content slides with the computed
   metrics and chart images, and saves the finished `.pptx`.

## Requirements

`pandas`, `geopandas`, `shapely`, `matplotlib`, `python-pptx`, `Pillow`.

## Notes

- `DEPLOYED_DEVICES` in `analyze.py` is a manually confirmed roster figure
  (devices issued for the round) — update it if the roster changes.
- The campaign footprint (`CAMPAIGN_STATES` in `analyze.py`) is the 15 states
  covered by this round: Kebbi, Niger, Jigawa, Bauchi, Zamfara, Sokoto, Kano,
  Yobe, Kaduna, Adamawa, Nasarawa, Kwara, Katsina, Borno, Gombe.
