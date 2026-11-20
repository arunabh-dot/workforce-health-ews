"""Workforce Health Early Warning System - Seeded Simulation Generator.

Simulates 30 sites across 5 districts over a 3-year timeline (2023-2025).
Injects 12-15 ground truth events (heat waves, industrial clusters, air quality episodes)
with realistic signal lags (environmental first -> clinic 1-2 days -> incidents/absence 2-4 days)
and missing-data gaps. Writes site_day and events_truth tables.
"""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import List, Dict, Any, Tuple
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from ews.config import load_settings
from ews.db import get_engine, init_db, SiteDay, EventTruth
from ews.ingest.weather import load_or_fetch_environmental_data, compute_heat_index


def generate_sites_metadata(settings, rng: np.random.Generator) -> pd.DataFrame:
    """Generate fixed metadata for 30 sites across 5 districts."""
    bbox = settings.district.bounding_box
    sites = []
    site_counter = 1

    district_names = [
        "North Logistics Port",
        "South Industrial Hub",
        "Eastern Construction Zone",
        "Western Maritime Terminal",
        "Central Manufacturing District",
    ]

    for d_idx, d_name in enumerate(district_names, start=1):
        for s_idx in range(1, settings.district.sites_per_district + 1):
            site_id = f"S{site_counter:02d}"
            # Jitter within bounding box
            lat = rng.uniform(bbox.lat_min + 0.05, bbox.lat_max - 0.05)
            lon = rng.uniform(bbox.lon_min + 0.05, bbox.lon_max - 0.05)
            # Headcount between 20 and 400 (heterogeneous across sites)
            base_headcount = int(rng.choice([
                rng.integers(30, 80),    # small site
                rng.integers(100, 220),  # medium site
                rng.integers(250, 400),  # large site
            ]))

            sites.append({
                "site_id": site_id,
                "district": f"District-{d_idx} ({d_name})",
                "district_id": f"D{d_idx}",
                "base_headcount": base_headcount,
                "lat": round(lat, 5),
                "lon": round(lon, 5),
            })
            site_counter += 1

    return pd.DataFrame(sites)


def define_ground_truth_events(dates: List[date], sites_df: pd.DataFrame, rng: np.random.Generator) -> List[Dict[str, Any]]:
    """Define 12-15 ground-truth events across 3 years.
    
    Types:
    - heat_wave: District or multi-district wide, 3-7 days, heat index up 4-8 C above seasonal norm
    - cluster: Localised 1-2 sites, 5-10 days, visits and incidents up 2-4x WITHOUT weather cause
    - air_quality: Regional / district PM2.5 spike, lagged rise in respiratory visits
    """
    total_days = len(dates)
    all_sites = sites_df["site_id"].tolist()
    districts = sites_df["district"].unique().tolist()
    
    events = []
    
    # We will plan ~13 events evenly spaced across the 3 years (approx 4-5 per year)
    # Ensure a good distribution between training (2023-2024) and test (2025) periods
    target_event_configs = [
        # Year 1 (2023)
        {"type": "heat_wave", "day_offset": 120, "duration": 5, "severity": 1.8, "desc": "Early summer heat dome in District 1 & 2"},
        {"type": "cluster", "day_offset": 180, "duration": 7, "severity": 2.5, "desc": "Cooling breakdown and intense overtime at site S03"},
        {"type": "air_quality", "day_offset": 240, "duration": 4, "severity": 2.0, "desc": "Regional dust storm causing PM2.5 particulate surge"},
        {"type": "heat_wave", "day_offset": 290, "duration": 6, "severity": 2.2, "desc": "Severe late summer heatwave across central districts"},
        
        # Year 2 (2024)
        {"type": "cluster", "day_offset": 420, "duration": 6, "severity": 2.8, "desc": "Hydration delivery failure and safety non-compliance at S15, S16"},
        {"type": "heat_wave", "day_offset": 500, "duration": 7, "severity": 2.4, "desc": "Extended high-humidity heatwave in coastal districts"},
        {"type": "air_quality", "day_offset": 580, "duration": 5, "severity": 2.1, "desc": "Industrial thermal inversion with severe particulate trapping"},
        {"type": "cluster", "day_offset": 640, "duration": 8, "severity": 3.0, "desc": "Confined space ventilation failure at site S22"},
        {"type": "heat_wave", "day_offset": 700, "duration": 5, "severity": 1.9, "desc": "Sudden unseasonal autumn temperature spike"},
        
        # Year 3 (2025 - Test Year)
        {"type": "heat_wave", "day_offset": 860, "duration": 5, "severity": 2.3, "desc": "Test Year Event 1: Pre-summer high humidity heatwave"},
        {"type": "cluster", "day_offset": 920, "duration": 7, "severity": 2.7, "desc": "Test Year Event 2: Localised industrial heat stress cluster at S07"},
        {"type": "heat_wave", "day_offset": 980, "duration": 6, "severity": 2.6, "desc": "Test Year Event 3: Peak summer extreme heat dome"},
        {"type": "air_quality", "day_offset": 1030, "duration": 5, "severity": 2.2, "desc": "Test Year Event 4: Hazardous particulate episode across Eastern Zone"},
        {"type": "cluster", "day_offset": 1070, "duration": 6, "severity": 2.4, "desc": "Test Year Event 5: Year-end turnaround maintenance cluster at S28, S29"},
    ]

    for idx, cfg in enumerate(target_event_configs, start=1):
        start_idx = min(cfg["day_offset"], total_days - 10)
        end_idx = min(start_idx + cfg["duration"] - 1, total_days - 1)
        start_dt = dates[start_idx]
        end_dt = dates[end_idx]
        
        event_type = cfg["type"]
        if event_type == "heat_wave":
            # District-wide: pick 1 or 2 adjacent districts
            chosen_district = rng.choice(districts)
            affected = sites_df[sites_df["district"] == chosen_district]["site_id"].tolist()
            if rng.random() > 0.5:
                # Include a second district
                other_districts = [d for d in districts if d != chosen_district]
                affected += sites_df[sites_df["district"] == rng.choice(other_districts)]["site_id"].tolist()
        elif event_type == "cluster":
            # 1 or 2 sites
            affected = rng.choice(all_sites, size=rng.choice([1, 2]), replace=False).tolist()
        else: # air_quality
            chosen_district = rng.choice(districts)
            affected = sites_df[sites_df["district"] == chosen_district]["site_id"].tolist()

        events.append({
            "event_id": f"EVT_{idx:02d}_{event_type.upper()}",
            "event_type": event_type,
            "start_date": start_dt,
            "end_date": end_dt,
            "affected_sites": affected,
            "severity": float(cfg["severity"]),
            "description": cfg["desc"],
        })

    return events


def generate_simulation_dataset(seed: int = 42) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """Generate the complete site_day dataset with seeded reproducibility."""
    settings = load_settings()
    rng = np.random.default_rng(seed)

    # 1. Load baseline environmental data (Dubai real weather)
    env_df = load_or_fetch_environmental_data()
    env_df["date"] = pd.to_datetime(env_df["date"]).dt.date
    dates = sorted(env_df["date"].unique().tolist())
    date_to_idx = {d: i for i, d in enumerate(dates)}

    # 2. Generate site metadata
    sites_df = generate_sites_metadata(settings, rng)
    
    # 3. Define 14 ground truth events
    events = define_ground_truth_events(dates, sites_df, rng)

    # Build event lookup masks:
    # event_heat_boost[site, date], event_pm25_boost[site, date]
    # event_clinic_multiplier[site, date], event_incident_multiplier[site, date], event_absence_boost[site, date]
    n_sites = len(sites_df)
    n_days = len(dates)
    site_ids = sites_df["site_id"].tolist()
    site_to_idx = {sid: i for i, sid in enumerate(site_ids)}

    # Arrays for event impacts with realistic lag structure:
    # Environmental impacts at day t:
    heat_index_boost = np.zeros((n_sites, n_days))
    pm25_boost = np.zeros((n_sites, n_days))

    # Workforce impacts (lagged):
    clinic_heat_mult = np.ones((n_sites, n_days))
    clinic_resp_mult = np.ones((n_sites, n_days))
    incident_mult = np.ones((n_sites, n_days))
    absence_rate_boost = np.zeros((n_sites, n_days))

    for ev in events:
        ev_start_idx = date_to_idx[ev["start_date"]]
        ev_end_idx = date_to_idx[ev["end_date"]]
        ev_type = ev["event_type"]
        sev = ev["severity"]

        for sid in ev["affected_sites"]:
            s_idx = site_to_idx[sid]
            for d in range(ev_start_idx, ev_end_idx + 1):
                if ev_type == "heat_wave":
                    # Environmental peak immediately (day t): +4 to +8 C
                    heat_index_boost[s_idx, d] += (4.0 + 2.0 * sev)
                    
                    # Clinic heat visits lag by 1 to 2 days:
                    for lag in [1, 2]:
                        if d + lag < n_days:
                            clinic_heat_mult[s_idx, d + lag] = max(
                                clinic_heat_mult[s_idx, d + lag], 1.8 + 1.2 * sev
                            )
                    # Incidents & absence lag by 2 to 4 days:
                    for lag in [2, 3, 4]:
                        if d + lag < n_days:
                            incident_mult[s_idx, d + lag] = max(
                                incident_mult[s_idx, d + lag], 1.6 + 0.8 * sev
                            )
                            absence_rate_boost[s_idx, d + lag] = max(
                                absence_rate_boost[s_idx, d + lag], 0.035 * sev
                            )

                elif ev_type == "cluster":
                    # Non-weather cause! Heat index normal, but clinic & incidents surge:
                    # Clinic visits lead first (day t):
                    clinic_heat_mult[s_idx, d] = max(
                        clinic_heat_mult[s_idx, d], 2.2 + 0.8 * sev
                    )
                    # Incidents and absence lag 1 to 3 days:
                    for lag in [1, 2, 3]:
                        if d + lag < n_days:
                            incident_mult[s_idx, d + lag] = max(
                                incident_mult[s_idx, d + lag], 2.0 + 1.0 * sev
                            )
                            absence_rate_boost[s_idx, d + lag] = max(
                                absence_rate_boost[s_idx, d + lag], 0.045 * sev
                            )

                elif ev_type == "air_quality":
                    # PM2.5 spikes on day t
                    pm25_boost[s_idx, d] += (65.0 * sev)
                    # Respiratory clinic visits lag by 1 to 2 days
                    for lag in [1, 2]:
                        if d + lag < n_days:
                            clinic_resp_mult[s_idx, d + lag] = max(
                                clinic_resp_mult[s_idx, d + lag], 2.2 + 1.1 * sev
                            )
                    # Absence lags 2 to 3 days
                    for lag in [2, 3]:
                        if d + lag < n_days:
                            absence_rate_boost[s_idx, d + lag] = max(
                                absence_rate_boost[s_idx, d + lag], 0.025 * sev
                            )

    # 4. Generate daily rows for every site and day
    # Pre-extract environmental vectors
    base_tmax = env_df["temp_max_c"].values
    base_rh = env_df["humidity_mean"].values
    base_hi = env_df["heat_index_c"].values
    base_pm25 = env_df["pm25"].values

    all_rows = []

    # One site designated with persistent bad data (e.g. S13: missing 35% of the time)
    bad_data_site = "S13"

    for _, site in sites_df.iterrows():
        sid = site["site_id"]
        s_idx = site_to_idx[sid]
        dist = site["district"]
        base_hc = site["base_headcount"]
        lat = site["lat"]
        lon = site["lon"]

        # Site-specific microclimate / micro-exposure variance
        site_tmax_offset = rng.normal(0, 0.4)
        site_pm25_offset = rng.normal(0, 2.5)

        # Baseline visit rate per 100 workers
        site_clinic_base_rate = rng.uniform(0.015, 0.035) # 1.5 to 3.5 visits per 100 workers/day
        site_incident_base_rate = rng.uniform(0.003, 0.008) # 0.3 to 0.8 incidents per 100 workers/day
        site_base_absence = rng.uniform(0.025, 0.045) # 2.5% to 4.5% baseline sick absence

        for d_idx, cur_date in enumerate(dates):
            # Headcount daily minor fluctuation (+/- 5%) and weekend drop
            weekday = cur_date.weekday() # 0 = Monday, 6 = Sunday
            # In Middle East / industrial UAE, Friday is half-day or rest, Sunday is work day.
            # Normal industrial operation:
            if weekday == 4: # Friday (reduced staff)
                active_hc = int(base_hc * 0.4)
            else:
                active_hc = max(10, int(base_hc * rng.uniform(0.95, 1.05)))

            # Environmental values with site offset + event boost
            hi_boost = heat_index_boost[s_idx, d_idx]
            site_hi = base_hi[d_idx] + hi_boost
            site_tmax = base_tmax[d_idx] + site_tmax_offset + (hi_boost * 0.6)
            site_rh = float(base_rh[d_idx])
            site_pm25 = max(5.0, base_pm25[d_idx] + site_pm25_offset + pm25_boost[s_idx, d_idx])

            # Comfort threshold logic:
            # Baseline clinic heat visits rising function of heat index above comfort threshold (~32C),
            # so ordinary hot summer days produce ordinary visits and don't flag anomalies.
            comfort_excess = max(0.0, site_hi - 32.0)
            heat_response = 1.0 + 0.08 * comfort_excess # steady predictable rise with temperature

            # Expected rates
            # 1. Clinic Heat Visits
            exp_heat_visits = (
                (active_hc / 100.0)
                * site_clinic_base_rate
                * heat_response
                * clinic_heat_mult[s_idx, d_idx]
            )
            clinic_heat_val = int(rng.poisson(max(0.01, exp_heat_visits)))

            # 2. Clinic Respiratory Visits
            # Moderate response to PM2.5 above 40 ug/m3
            pm25_excess = max(0.0, site_pm25 - 40.0)
            exp_resp_visits = (
                (active_hc / 100.0)
                * 0.012
                * (1.0 + 0.02 * pm25_excess)
                * clinic_resp_mult[s_idx, d_idx]
            )
            clinic_resp_val = int(rng.poisson(max(0.01, exp_resp_visits)))

            # 3. Incident Count (low-rate Poisson)
            exp_incidents = (
                (active_hc / 100.0)
                * site_incident_base_rate
                * (1.0 + 0.03 * comfort_excess)
                * incident_mult[s_idx, d_idx]
            )
            incident_val = int(rng.poisson(max(0.001, exp_incidents)))

            # 4. Absence Rate (seasonal + weekday effect + event boost)
            # Higher on Sundays / Mondays (start of week)
            weekday_effect = 0.008 if weekday in [0, 6] else -0.004
            # Seasonal term
            seasonal_term = 0.006 * np.sin(2 * np.pi * cur_date.timetuple().tm_yday / 365.25)
            clean_absence = (
                site_base_absence
                + weekday_effect
                + seasonal_term
                + absence_rate_boost[s_idx, d_idx]
                + rng.normal(0, 0.004)
            )
            absence_val = float(np.clip(clean_absence, 0.005, 0.35))

            # Missing-data gaps:
            # - Random 1 to 3 day outages per signal per site
            # - Site S13 has persistent bad data
            if sid == bad_data_site:
                avail_weather = rng.random() > 0.35
                avail_pm25 = rng.random() > 0.40
                avail_heat_vis = rng.random() > 0.35
                avail_resp_vis = rng.random() > 0.35
                avail_inc = rng.random() > 0.35
                avail_abs = rng.random() > 0.35
            else:
                # 2% random outage rate
                avail_weather = rng.random() > 0.015
                avail_pm25 = rng.random() > 0.02
                avail_heat_vis = rng.random() > 0.02
                avail_resp_vis = rng.random() > 0.02
                avail_inc = rng.random() > 0.02
                avail_abs = rng.random() > 0.02

            all_rows.append({
                "site_id": sid,
                "date": cur_date,
                "district": dist,
                "headcount": active_hc,
                "lat": lat,
                "lon": lon,
                "temp_max_c": round(site_tmax, 1) if avail_weather else np.nan,
                "humidity_mean": round(site_rh, 1) if avail_weather else np.nan,
                "heat_index_c": round(site_hi, 1) if avail_weather else np.nan,
                "pm25": round(site_pm25, 1) if avail_pm25 else np.nan,
                "clinic_heat_visits": clinic_heat_val if avail_heat_vis else -1,
                "clinic_resp_visits": clinic_resp_val if avail_resp_vis else -1,
                "incident_count": incident_val if avail_inc else -1,
                "absence_rate": round(absence_val, 4) if avail_abs else np.nan,
                "signal_available_weather": bool(avail_weather),
                "signal_available_pm25": bool(avail_pm25),
                "signal_available_clinic_heat": bool(avail_heat_vis),
                "signal_available_clinic_resp": bool(avail_resp_vis),
                "signal_available_incidents": bool(avail_inc),
                "signal_available_absence": bool(avail_abs),
            })

    site_day_df = pd.DataFrame(all_rows)
    return site_day_df, events


def plot_lag_structure(site_day_df: pd.DataFrame, events: List[Dict[str, Any]], output_path: Path):
    """Generate and save the diagnostic plot proving the realistic lag structure.
    
    Shows environmental spike -> clinic visits 1-2 days -> incidents 2-4 days later.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Pick a prominent heat wave event from training or test period
    hw_event = next(e for e in events if e["event_type"] == "heat_wave" and e["severity"] >= 2.0)
    target_site = hw_event["affected_sites"][0]
    
    # Filter 10 days before and 14 days after
    ev_start = hw_event["start_date"]
    start_window = ev_start - timedelta(days=5)
    end_window = hw_event["end_date"] + timedelta(days=8)
    
    sub = site_day_df[
        (site_day_df["site_id"] == target_site)
        & (site_day_df["date"] >= start_window)
        & (site_day_df["date"] <= end_window)
    ].sort_values("date").copy()

    # Normalize metrics to 0-1 for unified visual overlay
    dates = sub["date"]
    hi = sub["heat_index_c"].ffill().bfill().values
    clinic = sub["clinic_heat_visits"].replace(-1, np.nan).ffill().bfill().values
    incidents = sub["incident_count"].replace(-1, np.nan).ffill().bfill().values
    absence = sub["absence_rate"].ffill().bfill().values

    def norm(arr):
        mn, mx = np.nanmin(arr), np.nanmax(arr)
        return (arr - mn) / (mx - mn) if mx > mn else np.zeros_like(arr)

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=150)
    
    ax.plot(dates, norm(hi), color="red", marker="o", linewidth=2.5, label="Heat Index (Spikes Day 0)")
    ax.plot(dates, norm(clinic), color="darkorange", marker="s", linewidth=2.2, linestyle="--", label="Clinic Visits (Lags +1 to +2 Days)")
    ax.plot(dates, norm(incidents), color="purple", marker="^", linewidth=2.2, linestyle="-.", label="Incidents (Lags +2 to +4 Days)")
    ax.plot(dates, norm(absence), color="blue", marker="d", linewidth=1.8, linestyle=":", label="Absence Rate (Lags +2 to +4 Days)")

    ax.axvspan(hw_event["start_date"], hw_event["end_date"], color="red", alpha=0.12, label=f"True Event: {hw_event['event_id']}")
    
    ax.set_title(f"Simulated Multi-Signal Lag Structure (Site {target_site})\nEnvironmental Lead Time Before Workforce Harm", fontsize=12, fontweight="bold")
    ax.set_ylabel("Normalized Signal Intensity (0 to 1)", fontsize=10)
    ax.set_xlabel("Date", fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper left", frameon=True, framealpha=0.9)
    fig.autofmt_xdate()
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"Lag structure diagnostic plot saved to {output_path}")


def populate_database(site_day_df: pd.DataFrame, events: List[Dict[str, Any]], engine=None):
    """Write generated simulation to SQLite database."""
    if engine is None:
        engine = get_engine()
    init_db(engine)

    print(f"Writing {len(site_day_df)} records to site_day...")
    # SQLite write via pandas
    # Ensure -1 values in visits/incidents stay clean or None
    clean_df = site_day_df.copy()
    clean_df.loc[clean_df["clinic_heat_visits"] == -1, "clinic_heat_visits"] = None
    clean_df.loc[clean_df["clinic_resp_visits"] == -1, "clinic_resp_visits"] = None
    clean_df.loc[clean_df["incident_count"] == -1, "incident_count"] = None
    
    with engine.begin() as conn:
        conn.exec_driver_sql("DELETE FROM site_day")
        conn.exec_driver_sql("DELETE FROM events_truth")

    clean_df.to_sql("site_day", con=engine, if_exists="append", index=False)

    # Insert events into events_truth
    print(f"Writing {len(events)} events to events_truth...")
    truth_records = []
    for ev in events:
        truth_records.append({
            "event_id": ev["event_id"],
            "event_type": ev["event_type"],
            "start_date": ev["start_date"],
            "end_date": ev["end_date"],
            "affected_sites": json.dumps(ev["affected_sites"]),
            "severity": ev["severity"],
            "description": ev["description"],
        })
    pd.DataFrame(truth_records).to_sql("events_truth", con=engine, if_exists="append", index=False)
    print("Database population complete.")


def run_simulator(seed: int = 42):
    """Main simulation entrypoint."""
    settings = load_settings()
    used_seed = seed or settings.seeds.default_seed
    print(f"Running simulation with seed={used_seed}...")
    
    site_day_df, events = generate_simulation_dataset(seed=used_seed)
    
    # Save lag plot
    fig_path = Path(__file__).resolve().parent.parent / "validation" / "figures" / "lag_structure.png"
    plot_lag_structure(site_day_df, events, fig_path)
    
    # Populate DB
    populate_database(site_day_df, events)
    print(f"Simulation successfully finished: {len(site_day_df)} site-days, {len(events)} truth events.")
    return site_day_df, events


if __name__ == "__main__":
    run_simulator()
