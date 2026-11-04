import datetime as dt
import json
from pathlib import Path

import httpx

from app import store
from app.collectors.departures import upsert_departures
from app.connectors.base import JsonCache, make_client
from app.connectors.daylight import sun_times
from app.connectors.mvg import parse_departures
from app.connectors.open_meteo import OpenMeteo

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_mvg_departures():
    payload = json.loads((FIXTURES / "mvg_departures_marienplatz.json").read_text(encoding="utf-8"))
    df = parse_departures(payload, "de:09162:2")
    assert len(df) == len(payload)
    assert df["planned_utc"].notna().all()
    assert set(df.columns) >= {"line_id", "delay_min", "cancelled", "infos"}


def test_departure_upsert_updates_in_place():
    payload = json.loads((FIXTURES / "mvg_departures_marienplatz.json").read_text(encoding="utf-8"))
    df = parse_departures(payload, "de:09162:2")
    t0 = dt.datetime(2026, 11, 4, 7, 0)
    upsert_departures(df, t0)
    df2 = df.copy()
    df2["delay_min"] = 99
    upsert_departures(df2, t0 + dt.timedelta(minutes=2))
    rows = store.query_df("SELECT delay_min, n_obs, first_seen_utc, last_seen_utc FROM departures")
    assert len(rows) == len(df.drop_duplicates(["station_id", "line_id", "trip_code", "planned_utc"]))
    assert (rows["delay_min"] == 99).all() and (rows["n_obs"] == 2).all()
    assert (rows["last_seen_utc"] > rows["first_seen_utc"]).all()


def test_open_meteo_archive_long_format_and_cache(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request.url)
        return httpx.Response(200, json={"hourly": {
            "time": ["2025-01-10T00:00", "2025-01-10T01:00"],
            "temperature_2m": [-1.5, -2.0], "precipitation": [0.0, None],
        }})

    om = OpenMeteo(client=make_client(httpx.MockTransport(handler)), cache=JsonCache("om", root=tmp_path))
    args = (48.1, 11.5, dt.date(2025, 1, 10), dt.date(2025, 1, 10), "r1")
    df = om.archive(*args)
    assert len(df) == 4 and set(df["metric"]) == {"temperature_2m", "precipitation"}
    assert df["value"].isna().sum() == 1
    om.archive(*args)
    assert len(calls) == 1  # second call served from disk cache
    assert store.upsert_observations(df) == 4


def test_munich_january_daylight():
    t = sun_times(48.14, 11.58, dt.date(2027, 1, 10))
    assert dt.time(7, 45) < t["sunrise"].time() < dt.time(8, 15)
    assert dt.time(16, 30) < t["sunset"].time() < dt.time(16, 50)
