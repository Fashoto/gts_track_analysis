import pickle
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import os

EHA_BLUE = "#0090FC"
EHA_BLUE_80 = "#33A6FD"
EHA_BLUE_60 = "#66BCFD"
EHA_BLUE_40 = "#99D3FE"
EHA_BLUE_20 = "#CCE9FE"
EHA_GREEN = "#E2EE64"
BLACK = "#000000"
GREY = "#888888"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 12,
    "axes.edgecolor": GREY,
    "axes.labelcolor": BLACK,
    "text.color": BLACK,
    "xtick.color": BLACK,
    "ytick.color": BLACK,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
})

with open("/tmp/report_data_v3.pkl", "rb") as f:
    R = pickle.load(f)

os.makedirs("charts", exist_ok=True)

def save(fig, name):
    fig.tight_layout()
    fig.savefig(f"charts/{name}.png", dpi=200, transparent=False)
    plt.close(fig)

def fmt_thousands(x, pos):
    return f"{int(x):,}"

# 1. Daily trend
fig, ax = plt.subplots(figsize=(9, 4.2))
daily = R["daily"]
labels = [d.strftime("%a %d %b") for d in daily.index]
bars = ax.bar(labels, daily.values, color=EHA_BLUE, width=0.6)
for b, v in zip(bars, daily.values):
    ax.text(b.get_x()+b.get_width()/2, v + daily.max()*0.02, f"{v:,}", ha="center", va="bottom", fontsize=10)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_thousands))
ax.set_ylabel("GPS tracks recorded")
ax.set_ylim(0, daily.max()*1.18)
save(fig, "daily_trend")

# 2. State ranking
fig, ax = plt.subplots(figsize=(9, 5.2))
sg = R["state_grp"].sort_values("tracks", ascending=True)
bars = ax.barh(sg.index, sg["tracks"], color=EHA_BLUE)
for b, v in zip(bars, sg["tracks"]):
    ax.text(v + sg["tracks"].max()*0.01, b.get_y()+b.get_height()/2, f"{v:,}", va="center", fontsize=9)
ax.xaxis.set_major_formatter(mticker.FuncFormatter(fmt_thousands))
ax.set_xlabel("GPS tracks")
ax.set_xlim(0, sg["tracks"].max()*1.18)
save(fig, "state_ranking")

# 3. Day-one share by state (confirmed Sunday-start explanation)
fig, ax = plt.subplots(figsize=(9, 5.2))
d1 = R["day1_share_by_state"].sort_values()
colors = [EHA_BLUE if v >= 10 else EHA_GREEN for v in d1.values]
bars = ax.barh(d1.index, d1.values, color=colors)
ax.axvline(10, color=GREY, linestyle="--", linewidth=1)
for b, v in zip(bars, d1.values):
    ax.text(v + 0.6, b.get_y()+b.get_height()/2, f"{v:.1f}%", va="center", fontsize=9)
ax.set_xlabel("Share of a state's total tracks recorded on Day 1 (Sat 15 Aug)")
ax.set_xlim(0, d1.max()*1.2)
save(fig, "day1_share")

# 4. Continuity
fig, ax = plt.subplots(figsize=(8, 4.2))
cs = R["cont_summary"]
import matplotlib.colors as mcolors
cmap = mcolors.LinearSegmentedColormap.from_list("eha", [EHA_BLUE_40, EHA_BLUE])
bar_colors = [cmap(i / max(len(cs) - 1, 1)) for i in range(len(cs))]
bars = ax.bar(cs.index.astype(str), cs["track_share_pct"], color=bar_colors)
for b, v, c in zip(bars, cs["track_share_pct"], cs["count"]):
    ax.text(b.get_x()+b.get_width()/2, v+0.8, f"{v:.1f}%\n({c:,} codes)", ha="center", va="bottom", fontsize=9)
ax.set_xlabel("Distinct calendar days a team code appears on")
ax.set_ylabel("Share of total tracks")
ax.set_ylim(0, cs["track_share_pct"].max()*1.35)
save(fig, "continuity")

# 5. Effort distribution
fig, ax = plt.subplots(figsize=(9, 4.2))
tt = R["team_tracks"]
ax.hist(tt, bins=60, color=EHA_BLUE, edgecolor="white", linewidth=0.3)
ax.axvline(R["team_tracks_median"], color="#D64545", linestyle="--", linewidth=1.5, label=f"Median = {R['team_tracks_median']:.0f}")
ax.set_xlabel("Total GPS tracks per team code (round)")
ax.set_ylabel("Number of team codes")
ax.legend(frameon=False)
save(fig, "effort_hist")

# 6. Teams reporting per day
fig, ax = plt.subplots(figsize=(9, 4.2))
tpd = R["teams_per_day"]
labels = [d.strftime("%a %d %b") for d in tpd.index]
ax.plot(labels, tpd.values, color=EHA_BLUE, marker="o", linewidth=2.5, markersize=7)
for x, v in zip(labels, tpd.values):
    ax.text(x, v+120, f"{v:,}", ha="center", fontsize=9)
ax.set_ylabel("Distinct team codes reporting")
ax.set_ylim(0, tpd.max()*1.2)
save(fig, "teams_per_day")

# 7. Hour-of-day activity
fig, ax = plt.subplots(figsize=(9, 4.2))
hourly = R["hourly"].reindex(range(24), fill_value=0)
colors = [EHA_GREEN if 6 <= h <= 16 else EHA_BLUE_20 for h in hourly.index]
ax.bar(hourly.index, hourly.values, color=colors, width=0.75)
ax.set_xticks(range(0, 24, 2))
ax.set_xlabel("Hour of day (UTC)")
ax.set_ylabel("GPS tracks recorded")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_thousands))
save(fig, "hourly")

# 8. Data-quality overview
fig, ax = plt.subplots(figsize=(9, 4.6))
issues = [
    ("Malformed CSV rows\n(repaired)", R["repaired_pct"]),
    ("GPS/phone clock\nmismatch >30d", R["clock_mismatch_pct"]),
    ("Implausible speed\n(>30 m/s)", R["implausible_speed_pct"]),
    ("Poor accuracy\n(>50 m)", R["poor_accuracy_pct"]),
    ("Missing team\ncode", R["missing_team_code"]/R["n_total"]*100),
    ("Team code state\nunresolved", R["state_unmapped_rows"]/R["n_total"]*100),
]
labels = [i[0] for i in issues]
vals = [i[1] for i in issues]
bars = ax.bar(labels, vals, color=EHA_BLUE)
for b, v in zip(bars, vals):
    ax.text(b.get_x()+b.get_width()/2, v+0.05, f"{v:.2f}%", ha="center", va="bottom", fontsize=10)
ax.set_ylabel("Share of all GPS tracks")
ax.set_ylim(0, max(vals)*1.35)
plt.setp(ax.get_xticklabels(), fontsize=9.5)
save(fig, "qa_overview")

print("Charts written to charts/:")
for f in sorted(os.listdir("charts")):
    print(" -", f)
