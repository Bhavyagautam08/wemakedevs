"""
Renders a stored run (frontend_payload.json) to a PNG: plume density polygons, real particles,
per-cluster tracks, fire clusters and OSM schools reached, at +0/+3/+6/+9 h.
Independent of the frontend, so it shows exactly what the API returned.
  pip install matplotlib
  python ml-model/plot_run.py output/api-runs/<run_id>/frontend_payload.json run.png
"""
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

payload = json.load(open(sys.argv[1], encoding="utf-8"))
out = sys.argv[2]
p = payload["prediction"]
fig, axes = plt.subplots(1, 4, figsize=(22, 6), sharex=True, sharey=True)
fires = [f for f in p["map_geojson"]["features"] if f["properties"]["layer_type"] == "fire_source"]
for ax, h in zip(axes, [0, 3, 6, 9]):
    sl = next(s for s in p["timeline"] if s["horizon_offset_hours"] == h)
    for lvl in reversed(sl["heatmap_levels"]):
        for i, ring in enumerate(lvl.get("polygons", [])):
            xs, ys = zip(*ring)
            ax.fill(xs, ys, color=lvl["color"], alpha=0.3, label=f"{lvl['level']} >= {lvl.get('threshold_ugm3')}" if i == 0 else None)
    sc = sl["scatter_points"]
    ax.scatter([q[1] for q in sc], [q[0] for q in sc], s=4, c="k", alpha=0.5, label="particles (sample)")
    ax.scatter([f["geometry"]["coordinates"][0] for f in fires], [f["geometry"]["coordinates"][1] for f in fires],
               marker="^", c="red", s=40, label="fire clusters")
    hit = [s for s in p["schools"] if s["predicted_arrival_time"] and s["predicted_arrival_time"] <= sl["timestamp"]]
    ax.scatter([s["longitude"] for s in p["schools"]], [s["latitude"] for s in p["schools"]], s=3, c="#10b981", alpha=0.4)
    ax.scatter([s["longitude"] for s in hit], [s["latitude"] for s in hit], s=12, c="purple", label=f"schools reached ({len(hit)})")
    for line in sl["corridor_geojson"]["coordinates"]:
        ax.plot([c[0] for c in line], [c[1] for c in line], "b-", lw=1)
    w = next((x for x in p["weather"]["at_horizons"] if x["horizon_hours"] == h), None)
    ax.set_title(f"+{h}h  area {sl['plume_area_sq_km']} km2" + (f"  wind from {w['wind_direction_deg']}° {w['wind_speed_mps']} m/s" if w else ""))
    ax.legend(fontsize=7, loc="lower left")
fig.suptitle(f"{p['prediction_id']}  T0={p['valid_from']}  schools={len(p['schools'])}")
plt.tight_layout()
plt.savefig(out, dpi=80)
print(out)
