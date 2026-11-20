"""Test weather ingestion and Rothfusz heat index computation."""

import pytest
from pathlib import Path
import pandas as pd
from ews.ingest.weather import (
    compute_heat_index_single,
    WEATHER_PARQUET,
    AIR_QUALITY_PARQUET,
    ENVIRONMENT_PARQUET,
)


def test_parquet_files_exist():
    assert ENVIRONMENT_PARQUET.exists(), "Combined environmental parquet must exist"
    assert WEATHER_PARQUET.exists(), "Weather parquet must exist"
    assert AIR_QUALITY_PARQUET.exists(), "Air quality parquet must exist"

    df = pd.read_parquet(ENVIRONMENT_PARQUET)
    assert len(df) == 1096  # 3 full years (2023, 2024 leap year, 2025)
    for col in ["date", "temp_max_c", "humidity_mean", "pm25", "heat_index_c"]:
        assert col in df.columns


def test_heat_index_hand_computed_example():
    """Verify heat index matches NOAA hand-computed example within 0.5 deg C.

    Example: T = 35.0 C (95 F), RH = 60%.
    NOAA official heat index equation:
    HI_F = 113.09 F = 45.05 C.
    Official NOAA chart lists 114 F = 45.56 C.
    The formula is within 0.51 C of chart and exact to formula.
    """
    hi_c = compute_heat_index_single(35.0, 60.0)
    expected_hi_c = 45.05
    assert abs(hi_c - expected_hi_c) < 0.5, f"Expected ~{expected_hi_c} C, got {hi_c} C"

    # Additional standard check: T = 30.0 C, RH = 70%
    hi_c2 = compute_heat_index_single(30.0, 70.0)
    assert abs(hi_c2 - 35.04) < 0.5

    # Cool temperature check (should be close to temp)
    hi_cool = compute_heat_index_single(20.0, 50.0)
    assert abs(hi_cool - 20.0) < 1.0
