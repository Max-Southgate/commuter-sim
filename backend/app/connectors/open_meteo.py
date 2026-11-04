"""Open-Meteo: free, key-less weather API.

- Archive (ERA5 reanalysis, 1940-present, ~5 days lag): historical climatology.
- Forecast (up to 16 days): used in live mode (Phase 4).

Docs: https://open-meteo.com/en/docs/historical-weather-api
Note: ERA5 is a ~25 km grid, so it is representative of "Munich", not a specific street.
"""
from __future__ import annotations

import datetime as dt
import logging

import httpx
import pandas as pd

from app.connectors.base import JsonCache, get_json, make_client

log = logging.getLogger(__name__)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

HOURLY_VARS = [
    "temperature_2m",        # °C
    "apparent_temperature",  # °C, feels-like (wind chill / humidity)
    "precipitation",         # mm, sum over the PRECEDING hour
    "rain",                  # mm
    "snowfall",              # cm
    "snow_depth",            # m
    "wind_speed_10m",        # km/h
    "wind_gusts_10m",        # km/h
    "weather_code",          # WMO code
]

ARCHIVE_SOURCE = "open_meteo_archive"
FORECAST_SOURCE = "open_meteo_forecast"


def _to_long(payload: dict, source: str, location_id: str) -> pd.DataFrame:
    hourly = payload.get("hourly") or {}
    if not hourly.get("time"):
        return pd.DataFrame(columns=["source", "location_id", "metric", "ts", "value"])
    wide = pd.DataFrame(hourly)
    wide["ts"] = pd.to_datetime(wide.pop("time"))
    long = wide.melt(id_vars="ts", var_name="metric", value_name="value")
    long["value"] = pd.to_numeric(long["value"], errors="coerce").astype("float64")
    long["source"] = source
    long["location_id"] = location_id
    return long[["source", "location_id", "metric", "ts", "value"]]


class OpenMeteo:
    def __init__(self, client: httpx.Client | None = None, cache: JsonCache | None = None, timezone: str = "Europe/Berlin"):
        self.client = client or make_client()
        self.cache = cache if cache is not None else JsonCache("open_meteo")
        self.timezone = timezone

    def archive(self, lat: float, lon: float, start: dt.date, end: dt.date, location_id: str) -> pd.DataFrame:
        """Hourly historical weather, long format. Cached on disk (history doesn't change)."""
        params = {
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "hourly": ",".join(HOURLY_VARS),
            "timezone": self.timezone,
        }
        payload = get_json(self.client, ARCHIVE_URL, params, cache=self.cache)
        return _to_long(payload, ARCHIVE_SOURCE, location_id)

    def forecast(self, lat: float, lon: float, location_id: str, days: int = 16) -> pd.DataFrame:
        """Hourly forecast, long format. Never cached - it changes every few hours."""
        params = {
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "forecast_days": days,
            "hourly": ",".join(HOURLY_VARS),
            "timezone": self.timezone,
        }
        payload = get_json(self.client, FORECAST_URL, params, cache=None)
        return _to_long(payload, FORECAST_SOURCE, location_id)
