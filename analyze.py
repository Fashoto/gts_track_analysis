"""Full analytics pass over the refreshed Tracks_merged_clean.csv (export_1200_2026-08-20_12-01-03).
State/LGA/Ward now come from an exact point-in-polygon join against admin_boundary.sqlite
(done upstream, see tracks_df_v3_enriched.pkl), not team-code text parsing.
"""
import pandas as pd
import numpy as np
import pickle, os

DEPLOYED_DEVICES = 8023  # confirmed roster figure, distinct from distinct-IMEIs-observed-in-data

print("Loading data...")
df = pd.read_pickle("/tmp/tracks_df_v3_enriched.pkl")
n_total = len(df)
print(f"Loaded {n_total:,} rows")

R = {}
R["n_total"] = n_total
R["n_devices_deployed"] = DEPLOYED_DEVICES

# ------------------------------------------------------------------ state mapping (geometry-derived, already on df)
CAMPAIGN_STATES = ["Kebbi","Niger","Jigawa","Bauchi","Zamfara","Sokoto","Kano","Yobe",
                   "Kaduna","Adamawa","Nasarawa","Kwara","Katsina","Borno","Gombe"]

# Team-code prefix dictionary, used ONLY to override rows whose geometry-derived state
# falls outside the campaign footprint (e.g. a Kwara/Niger/Nasarawa team's ward polygon
# straddles into Oyo/Ekiti/FCT/Taraba/Benue near the state border). The team code is the
# ground truth for which state a team is assigned to; geometry just says where the point
# physically landed, which can legitimately cross a nearby border.
prefix_to_state = {
    "KB":"Kebbi",
    "KD":"Kaduna","KDN":"Kaduna","KAD":"Kaduna",
    "JGW":"Jigawa","JG":"Jigawa","JIG":"Jigawa",
    "BAU":"Bauchi","BA":"Bauchi",
    "KN":"Kano","KAN":"Kano",
    "ZAM":"Zamfara","ZM":"Zamfara",
    "NGR":"Niger","NIG":"Niger","NG":"Niger","NI":"Niger","NRG":"Niger","MGR":"Niger",
    "SKT":"Sokoto","SO":"Sokoto","STK":"Sokoto",
    "YB":"Yobe","YBE":"Yobe","YSF":"Yobe",
    "NSR":"Nasarawa","NAS":"Nasarawa","NRS":"Nasarawa",
    "KWR":"Kwara","KWA":"Kwara","KWARA":"Kwara",
    "ADM":"Adamawa","AD":"Adamawa","ADS":"Adamawa","ADW":"Adamawa","ADA":"Adamawa",
    "BOR":"Borno","BO":"Borno","BON":"Borno","BORNO":"Borno","BRN":"Borno",
    "GME":"Gombe","GMB":"Gombe","GM":"Gombe",
    "KTN":"Katsina","KT":"Katsina","KTS":"Katsina","KST":"Katsina",
}
SEPS = ["/", "_", "-", " "]

def resolve_state_from_teamcode(code):
    c = str(code).strip().upper()
    for sep in SEPS:
        if sep in c:
            seg = c.split(sep)[0].strip()
            if seg in prefix_to_state:
                return prefix_to_state[seg]
    if c in prefix_to_state:
        return prefix_to_state[c]
    return None

out_of_footprint_mask = df["State"].notna() & ~df["State"].isin(CAMPAIGN_STATES)
n_before_override = int(out_of_footprint_mask.sum())
teamcode_override = df.loc[out_of_footprint_mask, "Team Code"].map(resolve_state_from_teamcode)
recovered_mask = teamcode_override.notna()
df.loc[teamcode_override[recovered_mask].index, "State"] = teamcode_override[recovered_mask]
R["oof_recovered_by_teamcode"] = int(recovered_mask.sum())
R["oof_still_unresolved"] = n_before_override - R["oof_recovered_by_teamcode"]
R["oof_recovery_breakdown"] = teamcode_override[recovered_mask].value_counts()
R["oof_unresolved_codes"] = df.loc[teamcode_override[~recovered_mask].index, "Team Code"].value_counts()
print(f"Out-of-footprint override: {R['oof_recovered_by_teamcode']:,} of {n_before_override:,} "
      f"recovered to a campaign state via team code; {R['oof_still_unresolved']:,} still unresolved.")

mapped_mask = df["State"].notna()
R["state_mapped_pct"] = mapped_mask.mean() * 100
R["state_mapped_rows"] = int(mapped_mask.sum())
R["state_unmapped_rows"] = int((~mapped_mask).sum())
R["n_states"] = df["State"].nunique()

# ------------------------------------------------------------------ 1. at a glance
R["date_min"] = df["GPS Timestamp (UTC)"].min()
R["date_max"] = df["GPS Timestamp (UTC)"].max()
R["dates"] = sorted(df["Date"].unique())
R["n_team_codes"] = df["Team Code"].nunique()
R["n_imeis"] = df["IMEI"].nunique()
R["device_gap_vs_deployed"] = R["n_imeis"] - DEPLOYED_DEVICES

daily = df.groupby("Date").size()
R["daily"] = daily
R["peak_day"] = daily.idxmax()
R["peak_day_count"] = int(daily.max())
R["peak_day_share"] = daily.max() / n_total * 100

# ------------------------------------------------------------------ 2. data quality: repair + QA
R["repaired_rows"] = 16343
R["repaired_pct"] = R["repaired_rows"] / n_total * 100

R["clock_mismatch_30d"] = int((df["ts_diff_days"].abs() > 30).sum())
R["clock_mismatch_pct"] = R["clock_mismatch_30d"] / n_total * 100

R["neg_speed"] = int((df["Speed mps"] < 0).sum())
R["implausible_speed"] = int((df["Speed mps"] > 30).sum())
R["implausible_speed_pct"] = R["implausible_speed"] / n_total * 100

R["poor_accuracy_50m"] = int((df["Accuracy m"] > 50).sum())
R["poor_accuracy_pct"] = R["poor_accuracy_50m"] / n_total * 100

R["missing_team_code"] = int(df["Team Code"].isna().sum() + (df["Team Code"].astype(str).str.strip() == "").sum())

R["exact_dupes"] = int(df.duplicated(subset=[c for c in df.columns if c not in ("State","Date","ts_diff_days")], keep=False).sum())
R["dup_track_id"] = int(df["Track ID"].duplicated(keep=False).sum())

NIGERIA_LAT = (4.0, 14.0); NIGERIA_LON = (2.5, 14.8)
oob = (~df["Lat"].between(*NIGERIA_LAT)) | (~df["Lon"].between(*NIGERIA_LON))
R["out_of_bounds"] = int(oob.sum())

# ------------------------------------------------------------------ 3. state ranking
# Most geometry "out of footprint" rows were recovered above via team code (border-area
# wards). What's left here is genuinely unresolvable (e.g. dummy/test team codes).
out_of_footprint = df["State"].notna() & ~df["State"].isin(CAMPAIGN_STATES)
R["out_of_footprint_rows"] = int(out_of_footprint.sum())
R["out_of_footprint_by_state"] = df.loc[out_of_footprint, "State"].value_counts()

state_grp = df[df["State"].isin(CAMPAIGN_STATES)].groupby("State", observed=True).agg(
    tracks=("Track ID", "count"),
    teams=("Team Code", "nunique"),
    devices=("IMEI", "nunique"),
).sort_values("tracks", ascending=False)
state_grp["tracks_per_team"] = (state_grp["tracks"] / state_grp["teams"]).round(0)
state_grp["codes_minus_devices"] = state_grp["teams"] - state_grp["devices"]
R["state_grp"] = state_grp

# ------------------------------------------------------------------ 5. day-one signal (confirmed: some states launched Sunday, not Saturday)
day1 = R["dates"][0]
day_state = df[df["State"].isin(CAMPAIGN_STATES)].groupby(["State", "Date"], observed=True).size().unstack(fill_value=0)
day1_share = (day_state[day1] / day_state.sum(axis=1) * 100).sort_values()
R["day1_share_by_state"] = day1_share
R["day_state"] = day_state
R["sunday_start_states"] = list(day1_share[day1_share < 10].index)

# ------------------------------------------------------------------ 6. days-worked continuity
tc_days = df.groupby(["Team Code", "State"], observed=True)["Date"].nunique()
tc_tracks = df.groupby(["Team Code", "State"], observed=True).size()
continuity = pd.DataFrame({"days_worked": tc_days, "tracks": tc_tracks})
R["continuity"] = continuity
cont_summary = continuity.groupby("days_worked")["tracks"].agg(["count", "sum"])
cont_summary["track_share_pct"] = cont_summary["sum"] / cont_summary["sum"].sum() * 100
R["cont_summary"] = cont_summary

# ------------------------------------------------------------------ 8. distribution of effort
team_tracks = df.groupby("Team Code", observed=True).size()
R["team_tracks"] = team_tracks
R["team_tracks_median"] = team_tracks.median()
R["team_tracks_mean"] = team_tracks.mean()
R["team_tracks_p10"] = team_tracks.quantile(0.10)
R["team_tracks_p90"] = team_tracks.quantile(0.90)
low_vol = team_tracks[team_tracks < 50]
R["n_low_vol_teams"] = len(low_vol)
R["low_vol_track_share_pct"] = low_vol.sum() / n_total * 100

# ------------------------------------------------------------------ 9. team code integrity
# cross_state_codes uses the geometry-derived State, so it's a genuine operational
# finding now (a code whose tracks physically fall in >1 state), not a text-parsing artifact.
tc_state_lookup = df.groupby("Team Code", observed=True)["State"].agg(lambda s: s.dropna().unique())
cross_state_codes = tc_state_lookup[tc_state_lookup.apply(len) > 1]
R["cross_state_codes"] = len(cross_state_codes)

# "malformed"/"numeric-only" describe the TEXT quality of the code itself (a data-entry
# problem worth fixing even though geometry can now locate the track regardless).
numeric_only = df["Team Code"].astype(str).str.strip().str.match(r"^\d+$")
R["numeric_only_rows"] = int(numeric_only.sum())
R["malformed_rows"] = R["state_unmapped_rows"]  # tracks geometry itself couldn't place

dup_code_rows = df.groupby("Team Code", observed=True).size().sort_values(ascending=False)
R["top_duplicated_codes"] = dup_code_rows.head(15)

prefix_series = df["Team Code"].astype(str).str.strip().str.upper().str.split(r"[/_\- ]").str[0]
prefix_variety = df.assign(_prefix=prefix_series).groupby("State", observed=True)["_prefix"].nunique().sort_values(ascending=False)
R["prefix_variety_by_state"] = prefix_variety

# ------------------------------------------------------------------ device sharing: distinct team codes per IMEI
imei_tc = df.groupby("IMEI", observed=True)["Team Code"].nunique()
R["imei_multi_code_count"] = int((imei_tc > 1).sum())
R["imei_multi_code_pct"] = R["imei_multi_code_count"] / R["n_imeis"] * 100
R["imei_multi_code_max"] = int(imei_tc.max())

# ------------------------------------------------------------------ 12. day-to-day churn
codes_by_day = df.groupby("Date")["Team Code"].apply(lambda s: set(s.dropna().unique()))
churn_rows = []
dates_sorted = R["dates"]
for i in range(1, len(dates_sorted)):
    prev_set = codes_by_day[dates_sorted[i-1]]
    cur_set = codes_by_day[dates_sorted[i]]
    came_back = len(prev_set & cur_set)
    dropped = len(prev_set - cur_set)
    appeared = len(cur_set - prev_set)
    churn_rows.append((dates_sorted[i-1], dates_sorted[i], came_back, dropped, appeared))
R["churn"] = churn_rows

teams_per_day = df.groupby("Date")["Team Code"].nunique()
R["teams_per_day"] = teams_per_day
R["n_team_codes_round"] = df["Team Code"].nunique()

last_complete_day = dates_sorted[-2] if len(dates_sorted) >= 2 else dates_sorted[-1]
prior_days = dates_sorted[:-1]
worked_before = set(df.loc[df["Date"].isin(prior_days[:-1]), "Team Code"].dropna().unique()) if len(prior_days) > 1 else set()
worked_last_complete = set(df.loc[df["Date"] == last_complete_day, "Team Code"].dropna().unique())
missed_last_complete = worked_before - worked_last_complete
R["last_complete_day"] = last_complete_day
R["missed_on_last_complete_day"] = len(missed_last_complete)

# ------------------------------------------------------------------ 14. temporal / hour-of-day pattern
df["hour"] = df["GPS Timestamp (UTC)"].dt.hour
hourly = df.groupby("hour").size()
R["hourly"] = hourly

# ------------------------------------------------------------------ 15. gaps
df_sorted = df.sort_values(["Team Code", "GPS Timestamp (UTC)"])
gap_min = df_sorted.groupby("Team Code", observed=True)["GPS Timestamp (UTC)"].diff().dt.total_seconds() / 60
R["gap_gt_120min"] = int((gap_min > 120).sum())
R["gap_median"] = gap_min.median()

print("Saving results...")
with open("/tmp/report_data_v3.pkl", "wb") as f:
    pickle.dump(R, f)
df.to_pickle("/tmp/tracks_df_v3_final.pkl")
print("Done.")
print(f"Out-of-footprint tracks (resolved outside the 15 campaign states): {R['out_of_footprint_rows']:,}")
print(f"Devices deployed: {DEPLOYED_DEVICES:,} | Distinct IMEIs observed: {R['n_imeis']:,} | Gap: {R['device_gap_vs_deployed']:+,}")
print(f"Sunday-start states (Day1 share <10%): {R['sunday_start_states']}")
