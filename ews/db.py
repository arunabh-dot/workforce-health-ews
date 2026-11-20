"""Database models and SQLite connection setup for Workforce Health EWS."""

import json
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    Float,
    String,
    Date,
    DateTime,
    Boolean,
    Text,
    Index,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

Base = declarative_base()

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ews.db"


class SiteDay(Base):
    __tablename__ = "site_day"

    id = Column(Integer, primary_key=True, autoincrement=True)
    site_id = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    district = Column(String(50), nullable=False, index=True)
    headcount = Column(Integer, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)

    # Environmental signals
    temp_max_c = Column(Float, nullable=True)
    humidity_mean = Column(Float, nullable=True)
    heat_index_c = Column(Float, nullable=True)
    pm25 = Column(Float, nullable=True)

    # Workforce signals (simulated)
    clinic_heat_visits = Column(Integer, nullable=True)
    clinic_resp_visits = Column(Integer, nullable=True)
    incident_count = Column(Integer, nullable=True)
    absence_rate = Column(Float, nullable=True)

    # Availability flags (for missing data handling)
    signal_available_weather = Column(Boolean, default=True)
    signal_available_pm25 = Column(Boolean, default=True)
    signal_available_clinic_heat = Column(Boolean, default=True)
    signal_available_clinic_resp = Column(Boolean, default=True)
    signal_available_incidents = Column(Boolean, default=True)
    signal_available_absence = Column(Boolean, default=True)

    __table_args__ = (
        Index("idx_site_date", "site_id", "date", unique=True),
        Index("idx_district_date", "district", "date"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    site_id = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    level = Column(String(20), nullable=False)  # Watch, Warning, Critical
    score = Column(Float, nullable=False)  # Calibrated probability
    contributions = Column(Text, nullable=False)  # JSON dictionary of contributions
    action_id = Column(String(50), nullable=False)
    role = Column(String(100), nullable=False)
    confidence = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_alert_site_date", "site_id", "date"),
    )

    def get_contributions(self) -> Dict[str, Any]:
        return json.loads(self.contributions) if self.contributions else {}


class EventTruth(Base):
    """Simulator ground truth table.
    CRITICAL: Never read by the detector or production models! Only read by validation harness.
    """
    __tablename__ = "events_truth"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(50), nullable=False, unique=True)
    event_type = Column(String(50), nullable=False)  # heat_wave, cluster, air_quality
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    affected_sites = Column(Text, nullable=False)  # JSON list of site_ids
    severity = Column(Float, nullable=False)
    description = Column(String(255), nullable=True)

    def get_affected_sites(self) -> List[str]:
        return json.loads(self.affected_sites) if self.affected_sites else []


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_role = Column(String(50), nullable=False)
    view = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


def get_engine(db_path: Optional[Path] = None):
    target_path = db_path or DEFAULT_DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{target_path.as_posix()}", echo=False)


def get_session(engine=None) -> Session:
    if engine is None:
        engine = get_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionLocal()


def init_db(engine=None):
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(bind=engine)
