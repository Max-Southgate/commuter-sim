"""Load the YAML config that drives everything (routes, thresholds, collector settings).

Resolution order: $COMMUTER_CONFIG, then config/routes.yaml, then config/routes.example.yaml.
"""
from __future__ import annotations

import datetime as dt
import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
DATA_DIR = Path(os.environ.get("COMMUTER_DATA_DIR", REPO_ROOT / "data"))

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


@dataclass(frozen=True)
class Point:
    lat: float
    lon: float
    label: str = ""


@dataclass(frozen=True)
class Route:
    id: str
    name: str
    home: Point
    work: Point
    stops: tuple[str, ...]
    period_start: dt.date
    period_end: dt.date
    out_time: dt.time
    back_time: dt.time
    commute_minutes: int
    workdays: tuple[int, ...]  # 0 = Monday

    @property
    def midpoint(self) -> Point:
        return Point((self.home.lat + self.work.lat) / 2, (self.home.lon + self.work.lon) / 2, "midpoint")

    def commute_days(self) -> list[dt.date]:
        """Working days in the stay period (public holidays are handled by the events layer later)."""
        days, d = [], self.period_start
        while d <= self.period_end:
            if d.weekday() in self.workdays:
                days.append(d)
            d += dt.timedelta(days=1)
        return days


@dataclass(frozen=True)
class CyclingThresholds:
    min_temp_c: float = -3.0          # feels-like temperature
    max_precip_mm_h: float = 0.2
    max_gust_kmh: float = 50.0
    max_snow_depth_cm: float = 3.0   # ERA5 grid snow depth; city streets are usually cleared sooner


@dataclass(frozen=True)
class CollectorSettings:
    interval_seconds: int = 120
    windows: tuple[tuple[dt.time, dt.time], ...] = ()
    weekdays_only: bool = True
    departures_per_poll: int = 60


@dataclass(frozen=True)
class Settings:
    source_file: Path
    timezone: str
    routes: dict[str, Route]
    thresholds: CyclingThresholds
    first_year: int
    last_year: int
    collector: CollectorSettings = field(default_factory=CollectorSettings)

    def route(self, route_id: str | None = None) -> Route:
        if route_id is None:
            return next(iter(self.routes.values()))
        try:
            return self.routes[route_id]
        except KeyError:
            raise KeyError(f"Unknown route '{route_id}'. Known: {', '.join(self.routes)}") from None


def _time(s) -> dt.time:
    return dt.time.fromisoformat(str(s))


def _date(v) -> dt.date:
    return v if isinstance(v, dt.date) else dt.date.fromisoformat(str(v))


def _point(d: dict) -> Point:
    return Point(float(d["lat"]), float(d["lon"]), d.get("label", ""))


def parse_settings(raw: dict, source_file: Path) -> Settings:
    routes = {}
    for rid, r in (raw.get("routes") or {}).items():
        routes[rid] = Route(
            id=rid,
            name=r.get("name", rid),
            home=_point(r["home"]),
            work=_point(r["work"]),
            stops=tuple(str(s) for s in (r.get("stops") or [])),
            period_start=_date(r["period"]["start"]),
            period_end=_date(r["period"]["end"]),
            out_time=_time(r["commute_times"]["out"]),
            back_time=_time(r["commute_times"]["back"]),
            commute_minutes=int(r.get("commute_minutes", 30)),
            workdays=tuple(WEEKDAYS.index(w.lower()[:3]) for w in r.get("workdays", WEEKDAYS[:5])),
        )
    if not routes:
        raise ValueError(f"No routes defined in {source_file}")

    th = raw.get("cycling_thresholds") or {}
    clim = raw.get("climatology") or {}
    col = raw.get("collector") or {}
    windows = []
    for w in col.get("windows", ["06:00-10:00", "15:00-20:00"]):
        a, b = w.split("-")
        windows.append((_time(a), _time(b)))

    return Settings(
        source_file=source_file,
        timezone=raw.get("timezone", "Europe/Berlin"),
        routes=routes,
        thresholds=CyclingThresholds(
            **{k: v for k, v in th.items() if k in CyclingThresholds.__dataclass_fields__}
        ),
        first_year=int(clim.get("first_year", 1996)),
        last_year=int(clim.get("last_year", dt.date.today().year - 1)),
        collector=CollectorSettings(
            interval_seconds=int(col.get("interval_seconds", 120)),
            windows=tuple(windows),
            weekdays_only=bool(col.get("weekdays_only", True)),
            departures_per_poll=int(col.get("departures_per_poll", 60)),
        ),
    )


def config_path() -> Path:
    if env := os.environ.get("COMMUTER_CONFIG"):
        return Path(env)
    real = CONFIG_DIR / "routes.yaml"
    if real.exists():
        return real
    log.warning("config/routes.yaml not found - using routes.example.yaml (example coordinates!)")
    return CONFIG_DIR / "routes.example.yaml"


@lru_cache
def get_settings() -> Settings:
    path = config_path()
    with open(path, encoding="utf-8") as f:
        return parse_settings(yaml.safe_load(f), path)
