"""MVG (Münchner Verkehrsgesellschaft) departures API.

This is the unofficial JSON API behind mvg.de. It covers U-Bahn, tram, bus AND S-Bahn
(S-Bahn data comes from DB). It has no history, which is why we collect it ourselves.
Be polite: poll a handful of stations every couple of minutes, nothing more.

Endpoints (observed Nov 2026):
  /api/bgw-pt/v3/departures?globalId=de:09162:2&limit=60
  /api/bgw-pt/v3/locations?query=Marienplatz&locationTypes=STATION
  /api/bgw-pt/v3/stations/nearby?latitude=..&longitude=..
"""
from __future__ import annotations

import datetime as dt
import json

import httpx
import pandas as pd

from app.connectors.base import get_json, make_client

BASE = "https://www.mvg.de/api/bgw-pt/v3"

DEPARTURE_COLUMNS = [
    "station_id", "line_id", "trip_code", "planned_utc", "label", "transport_type",
    "destination", "platform", "realtime", "delay_min", "realtime_utc", "cancelled", "sev", "infos",
]


def _ms_to_utc(ms) -> dt.datetime | None:
    if ms is None:
        return None
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).replace(tzinfo=None)


def parse_departures(payload: list[dict], station_id: str) -> pd.DataFrame:
    rows = []
    for d in payload:
        planned = _ms_to_utc(d.get("plannedDepartureTime"))
        if planned is None:
            continue
        infos = [i.get("message") for i in (d.get("infos") or []) if i.get("message")]
        infos += [m.get("text", m) if isinstance(m, dict) else m for m in (d.get("messages") or [])]
        rows.append({
            "station_id": d.get("stationGlobalId") or station_id,
            "line_id": d.get("lineId") or f"{d.get('transportType')}:{d.get('label')}",
            "trip_code": int(d.get("tripCode") or 0),
            "planned_utc": planned,
            "label": d.get("label"),
            "transport_type": d.get("transportType"),
            "destination": d.get("destination"),
            "platform": None if d.get("platform") is None else str(d.get("platform")),
            "realtime": bool(d.get("realtime")),
            "delay_min": d.get("delayInMinutes"),
            "realtime_utc": _ms_to_utc(d.get("realtimeDepartureTime")),
            "cancelled": bool(d.get("cancelled")),
            "sev": bool(d.get("sev")),
            "infos": json.dumps(infos, ensure_ascii=False),
        })
    df = pd.DataFrame(rows, columns=DEPARTURE_COLUMNS)
    df["delay_min"] = pd.to_numeric(df["delay_min"], errors="coerce").astype("Int64")
    return df


class MVG:
    def __init__(self, client: httpx.Client | None = None):
        self.client = client or make_client(timeout=15.0)

    def departures(self, station_id: str, limit: int = 60) -> pd.DataFrame:
        payload = get_json(self.client, f"{BASE}/departures", {"globalId": station_id, "limit": limit})
        return parse_departures(payload, station_id)

    def search_stations(self, query: str) -> list[dict]:
        return get_json(self.client, f"{BASE}/locations", {"query": query, "locationTypes": "STATION"})

    def nearby_stations(self, lat: float, lon: float) -> list[dict]:
        return get_json(self.client, f"{BASE}/stations/nearby", {"latitude": lat, "longitude": lon})
