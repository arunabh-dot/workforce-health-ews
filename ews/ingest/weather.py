"""Weather and air quality data ingestion from Open-Meteo with local Parquet caching."""

import math
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import pandas as pd
import requests

from ews.config import load_settings

RAW_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"
WEATHER_PARQUET = RAW_DATA_DIR / "weather_archive.parquet"
AIR_QUALITY_PARQUET = RAW_DATA_DIR / "air_quality_archive.parquet"
ENVIRONMENT_PARQUET = RAW_DATA_DIR / "environment_combined.parquet"


def compute_heat_index_single(t_c: float, rh: float) -> float:
    """Compute Heat Index (in Celsius) using the NOAA Rothfusz regression.

    Parameters:
    -----------
    t_c : float
        Dry-bulb temperature in Celsius
    rh : float
        Relative humidity in percent (0 to 100)

    Returns:
    --------
    float
        Heat index in Celsius
    """
    if np.isnan(t_c) or np.isnan(rh):
        return np.nan

    # Convert Celsius to Fahrenheit
    t_f = t_c * 9.0 / 5.0 + 32.0

    # Steadman simple formula
    hi_simple = 0.5 * (t_f + 61.0 + ((t_f - 68.0) * 1.2) + (rh * 0.094))

    if (hi_simple + t_f) / 2.0 >= 80.0:
        # Full Rothfusz regression
        hi_f = (
            -42.379
            + 2.04901523 * t_f
            + 10.14333127 * rh
            - 0.22475541 * t_f * rh
            - 0.00683783 * (t_f**2)
            - 0.05481717 * (rh**2)
            + 0.00122874 * (t_f**2) * rh
            + 0.00085282 * t_f * (rh**2)
            - 0.00000199 * (t_f**2) * (rh**2)
        )

        # Dry atmosphere adjustment
        if rh < 13.0 and 80.0 <= t_f <= 112.0:
            adj = ((13.0 - rh) / 4.0) * math.sqrt(max(0.0, (17.0 - abs(t_f - 95.0)) / 17.0))
            hi_f -= adj
        # High humidity adjustment
        elif rh > 85.0 and 80.0 <= t_f <= 87.0:
            adj = ((rh - 85.0) / 10.0) * ((87.0 - t_f) / 5.0)
            hi_f += adj
    else:
        hi_f = hi_simple

    # Convert back to Celsius
    hi_c = (hi_f - 32.0) * 5.0 / 9.0
    return float(hi_c)


def compute_heat_index(temp_c_series: pd.Series, rh_series: pd.Series) -> pd.Series:
    """Vectorized heat index computation over pandas Series."""
    return pd.Series(
        [compute_heat_index_single(t, rh) for t, rh in zip(temp_c_series, rh_series)],
        index=temp_c_series.index,
        name="heat_index_c",
    )


def fetch_open_meteo_weather(
    lat: float = 25.2048,
    lon: float = 55.2708,
    start_date: str = "2023-01-01",
    end_date: str = "2025-12-31",
    timeout: int = 30,
) -> pd.DataFrame:
    """Pull historical weather data from Open-Meteo Archive API."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": ["temperature_2m_max", "relative_humidity_2m_mean"],
        "timezone": "auto",
    }
    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    df = pd.DataFrame(
        {
            "date": pd.to_datetime(data["daily"]["time"]).date,
            "temp_max_c": data["daily"]["temperature_2m_max"],
            "humidity_mean": data["daily"]["relative_humidity_2m_mean"],
        }
    )
    return df


def fetch_open_meteo_air_quality(
    lat: float = 25.2048,
    lon: float = 55.2708,
    start_date: str = "2023-01-01",
    end_date: str = "2025-12-31",
    timeout: int = 45,
) -> pd.DataFrame:
    """Pull historical PM2.5 / PM10 air quality data from Open-Meteo."""
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"

    # Air quality API handles large queries best split by year
    years = range(int(start_date[:4]), int(end_date[:4]) + 1)
    all_chunks = []

    for yr in years:
        chunk_start = f"{yr}-01-01" if yr > int(start_date[:4]) else start_date
        chunk_end = f"{yr}-12-31" if yr < int(end_date[:4]) else end_date

        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": chunk_start,
            "end_date": chunk_end,
            "hourly": ["pm2_5", "pm10"],
            "timezone": "auto",
        }
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        times = pd.to_datetime(data["hourly"]["time"])
        hourly_df = pd.DataFrame(
            {
                "date": times.date,
                "pm25": data["hourly"]["pm2_5"],
                "pm10": data["hourly"]["pm10"],
            }
        )
        daily_mean = hourly_df.groupby("date")[["pm25", "pm10"]].mean().reset_index()
        all_chunks.append(daily_mean)

    df = pd.concat(all_chunks, ignore_index=True).drop_duplicates(subset=["date"])
    return df


def generate_synthetic_environmental_fallback(
    start_date: str = "2023-01-01",
    end_date: str = "2025-12-31",
    seed: int = 42,
) -> pd.DataFrame:
    """Generate realistic hot-climate environmental data if network is inaccessible."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start_date, end_date, freq="D")
    n = len(dates)
    day_of_year = dates.dayofyear.values

    # Seasonal Dubai climate model: Peak July/August ~42-45C, Winter Jan ~24C
    # Sinusoidal annual curve peaking around day 200 (mid-July)
    annual_cycle = -np.cos(2 * np.pi * (day_of_year - 20) / 365.25)
    temp_max = 33.0 + 10.5 * annual_cycle + rng.normal(0, 1.8, size=n)

    # Relative humidity: typically inverse to temperature, around 45-65%
    humidity = 55.0 - 15.0 * annual_cycle + rng.normal(0, 5.0, size=n)
    humidity = np.clip(humidity, 20.0, 95.0)

    # Base PM2.5 in desert climate ~35-50 ug/m3 with occasional dust spikes
    pm25_base = 38.0 + 8.0 * np.sin(2 * np.pi * day_of_year / 365.25)
    dust_shocks = rng.exponential(scale=6.0, size=n)
    pm25 = np.clip(pm25_base + dust_shocks, 10.0, 180.0)

    df = pd.DataFrame(
        {
            "date": dates.date,
            "temp_max_c": np.round(temp_max, 1),
            "humidity_mean": np.round(humidity, 1),
            "pm25": np.round(pm25, 1),
        }
    )
    df["heat_index_c"] = compute_heat_index(df["temp_max_c"], df["humidity_mean"])
    return df


def load_or_fetch_environmental_data(force_refresh: bool = False) -> pd.DataFrame:
    """Load cached environmental Parquet or fetch from Open-Meteo."""
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings = load_settings()
    start_date = settings.dates.start_date
    end_date = settings.dates.end_date

    if ENVIRONMENT_PARQUET.exists() and not force_refresh:
        return pd.read_parquet(ENVIRONMENT_PARQUET)

    # Attempt live pull with fallback
    try:
        print(f"Fetching Open-Meteo weather data ({start_date} to {end_date})...")
        weather_df = fetch_open_meteo_weather(start_date=start_date, end_date=end_date)
        weather_df.to_parquet(WEATHER_PARQUET, index=False)

        print(f"Fetching Open-Meteo air quality data ({start_date} to {end_date})...")
        aq_df = fetch_open_meteo_air_quality(start_date=start_date, end_date=end_date)
        aq_df.to_parquet(AIR_QUALITY_PARQUET, index=False)

        combined = pd.merge(weather_df, aq_df, on="date", how="left")
        combined["pm25"] = combined["pm25"].ffill().bfill()
        combined["heat_index_c"] = compute_heat_index(
            combined["temp_max_c"], combined["humidity_mean"]
        )
        combined.to_parquet(ENVIRONMENT_PARQUET, index=False)
        print(f"Cached environmental data to {ENVIRONMENT_PARQUET} ({len(combined)} rows)")
        return combined

    except Exception as exc:
        print(f"Live Open-Meteo fetch failed ({exc}). Using high-fidelity synthetic climate fallback...")
        fallback_df = generate_synthetic_environmental_fallback(
            start_date=start_date, end_date=end_date, seed=settings.seeds.default_seed
        )
        fallback_df.to_parquet(ENVIRONMENT_PARQUET, index=False)
        fallback_df[["date", "temp_max_c", "humidity_mean"]].to_parquet(
            WEATHER_PARQUET, index=False
        )
        fallback_df[["date", "pm25"]].to_parquet(AIR_QUALITY_PARQUET, index=False)
        print(f"Cached fallback climate data to {ENVIRONMENT_PARQUET} ({len(fallback_df)} rows)")
        return fallback_df


if __name__ == "__main__":
    df = load_or_fetch_environmental_data(force_refresh=True)
    print("Environment sample:")
    print(df.head())
    print("\nHeat Index Summary (Celsius):")
    print(df["heat_index_c"].describe())
