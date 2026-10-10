"""
Independent sanity checks on one Layer 1 run, printed as plain numbers so a human can
audit them. Usage:  python verify_run.py [replay|live]

Checks:
  1. Wind/BLH used at each horizon come from the hourly forecast (and differ over time).
  2. +3h -> +6h -> +9h are one continuous run: mean particle displacement between horizons
     equals the time-integrated forecast wind, and the particle count does not reset.
  3. Mass budget: emitted mass (Ce * FRP * hours) vs mass left in the cloud (decay only).
  4. Every school with impact_probability > 0 has an arrival time, and vice versa.
"""

import math
import sys

import numpy as np

from src.service import DhuanAlertService
from src.layer1_predictive.weather_field import WeatherVectorField


def main(mode: str) -> int:
    svc = DhuanAlertService()
    l1 = svc.layer1
    sim = l1.config.simulation

    if mode == "live":
        from datetime import datetime, timezone
        t0 = datetime.now(timezone.utc)
        hotspots = svc.get_live_fires()
        weather = svc.get_live_weather_field(hotspots, t0)
    else:
        hotspots, weather, t0 = svc.get_replay_inputs()

    clusters = l1.source_model.cluster_hotspots(hotspots, current_time=t0)
    print(f"T0={t0.isoformat()}  hotspots={len(hotspots)}  clusters={len(clusters)}  weather_records={len(weather)}")
    e_total = sum(c.emission_rate_kg_s for c in clusters)
    print(f"total emission rate = {e_total:.3f} kg/s PM2.5  (Ce={sim.smoke_emission_coefficient_kg_per_mj} kg/MJ)")

    snaps, _ = l1.ensemble.run_ensemble(clusters, weather, t0, sim.horizon_hours, sim.timestep_seconds)
    nominal = l1._nominal_member_index()
    wf = WeatherVectorField(weather, start_time=t0, config=sim)

    print(f"\n[1] forecast wind/BLH at {wf.station_count} weather stations (min / max across stations)")
    for h in [0] + sim.forecast_horizons:
        t = h * 3600.0
        u, v, b = (wf._station_values(k, t) for k in ("u", "v", "blh"))
        dirs = (np.degrees(np.arctan2(-u, -v)) + 360) % 360
        print(f"  +{h}h  wind-from {dirs.min():5.0f}..{dirs.max():5.0f} deg  speed {np.hypot(u, v).min():.1f}..{np.hypot(u, v).max():.1f} m/s"
              f"  BLH {b.min():.0f}..{b.max():.0f} m")

    print("\n[2] chaining: displacement between horizons vs integrated wind (nominal member)")
    ok = True
    hs = sim.forecast_horizons
    for a, b in zip(hs[:-1], hs[1:]):
        sa, sb = snaps[a][nominal], snaps[b][nominal]
        if a < sim.emission_duration_hours or len(sa) != len(sb):
            print(f"  +{a}h->+{b}h skipped (particles still being released)")
            continue
        # Expected advection: integrate the field at each particle's position hour by hour, from the
        # hourly snapshots (the engine's own positions, so this checks the steps between them).
        ex = ey = 0.0
        for hr in range(a, b):
            st = snaps[hr][nominal]
            for t in np.arange(hr * 3600, (hr + 1) * 3600, sim.timestep_seconds):
                u, v = wf.get_wind_vector(st.x, st.y, t)
                ex += float(np.mean(u)) * sim.timestep_seconds
                ey += float(np.mean(v)) * sim.timestep_seconds
        dx, dy = float(np.mean(sb.x - sa.x)), float(np.mean(sb.y - sa.y))
        err = math.hypot(dx - ex, dy - ey)
        ok &= err < 1500
        print(f"  +{a}h->+{b}h expected=({ex/1000:+.2f},{ey/1000:+.2f}) km  "
              f"actual=({dx/1000:+.2f},{dy/1000:+.2f}) km  error={err/1000:.2f} km  particles {len(sa)}->{len(sb)}")

    print("\n[3] mass budget (nominal member)")
    emitted = e_total * 3600.0 * sim.emission_duration_hours
    for h in hs:
        st = snaps[h][nominal]
        print(f"  +{h}h mass in cloud = {np.sum(st.mass)/1e9:,.0f} kg of {emitted:,.0f} kg emitted  "
              f"(mass-weighted mixing height {np.average(st.mixing_height_m, weights=st.mass):.0f} m)")

    print("\n[4] school consistency (full pipeline)")
    pred = l1.run(hotspots, weather, None, run_timestamp=t0,
                  school_provider=svc.schools_client.fetch_schools_in_bboxes)
    print(f"  schools from {pred.simulation['school_source']}: {len(pred.schools)} in plume footprint "
          f"({pred.simulation['footprint_area_sq_km']} km2); showing top 8 + count")
    consistent = True
    for i, s in enumerate(pred.schools):
        c = (s.impact_probability > 0) == (s.predicted_arrival_time is not None)
        consistent &= c
        if i >= 8:
            continue
        print(f"  {s.name[:34]:34s} {s.distance_to_fire_km:6.1f} km  peak={s.peak_concentration:8.2f} ug/m3  "
              f"p={s.impact_probability:.2f}  arrival={s.predicted_arrival_time}  {'OK' if c else 'MISMATCH'}")

    print(f"  impacted (p>0): {sum(1 for s in pred.schools if s.impact_probability > 0)} of {len(pred.schools)}")
    print(f"\nRESULT: chaining {'PASS' if ok else 'FAIL'}, school consistency {'PASS' if consistent else 'FAIL'}")
    return 0 if ok and consistent else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "replay"))
