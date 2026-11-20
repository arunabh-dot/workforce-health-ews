"""Configuration loader using Pydantic and PyYAML."""

from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
from pydantic import BaseModel, Field

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
SETTINGS_PATH = CONFIG_DIR / "settings.yaml"
PLAYBOOK_PATH = CONFIG_DIR / "playbook.yaml"


class BoundingBoxConfig(BaseModel):
    lat_min: float = 24.95
    lat_max: float = 25.35
    lon_min: float = 55.10
    lon_max: float = 55.50


class DistrictConfig(BaseModel):
    name: str = "Al-Sharq Industrial Zone"
    city: str = "Dubai"
    bounding_box: BoundingBoxConfig = Field(default_factory=BoundingBoxConfig)
    num_districts: int = 5
    sites_per_district: int = 6
    total_sites: int = 30


class DatesConfig(BaseModel):
    start_date: str = "2023-01-01"
    train_end_date: str = "2024-12-31"
    test_start_date: str = "2025-01-01"
    end_date: str = "2025-12-31"


class EnvironmentConfig(BaseModel):
    heat_index_high_risk_threshold_c: float = 41.0
    pm25_unhealthy_threshold: float = 55.5


class CusumConfig(BaseModel):
    k: float = 0.5
    h: float = 4.0


class EwmaConfig(BaseModel):
    lambda_: float = 0.3


class AlertingConfig(BaseModel):
    watch_threshold: float = 0.25          # lowered to catch early signals
    warning_threshold: float = 0.40        # lowered for higher sensitivity
    critical_threshold: float = 0.70       # slightly relaxed for small event set
    consecutive_days_required: int = 2
    workforce_contribution_critical_min: float = 0.20  # easier to reach Critical
    max_alerts_per_district_per_week: int = 5
    confidence_penalty_missing_signal: float = 0.7
    confidence_penalty_district_fallback: float = 0.8


class BaselineConfig(BaseModel):
    min_history_days: int = 120
    rolling_window_days: int = 365
    exclusion_buffer_days: int = 14
    fourier_harmonics: int = 2


class SeedsConfig(BaseModel):
    default_seed: int = 42
    robustness_seeds: List[int] = Field(default_factory=lambda: [42, 101, 2024, 777, 999])


class Settings(BaseModel):
    district: DistrictConfig = Field(default_factory=DistrictConfig)
    dates: DatesConfig = Field(default_factory=DatesConfig)
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    cusum: CusumConfig = Field(default_factory=CusumConfig)
    ewma: EwmaConfig = Field(default_factory=EwmaConfig)
    alerting: AlertingConfig = Field(default_factory=AlertingConfig)
    baseline: BaselineConfig = Field(default_factory=BaselineConfig)
    seeds: SeedsConfig = Field(default_factory=SeedsConfig)


def load_settings(path: Optional[Path] = None) -> Settings:
    target_path = path or SETTINGS_PATH
    if not target_path.exists():
        return Settings()
    with open(target_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return Settings(**data)


def load_playbook(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    target_path = path or PLAYBOOK_PATH
    if not target_path.exists():
        return []
    with open(target_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("rules", [])
