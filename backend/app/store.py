"""DuckDB-backed store. One file, no server.

DuckDB allows only one writing process at a time, so connections are short-lived
(open -> do work -> close) and retried briefly if the file is locked. This lets the
collector process and the API server share the same file.
"""
from __future__ import annotations

import contextlib
import logging
import time
from pathlib import Path
from typing import Iterator

import duckdb
import pandas as pd

from app import config

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    source      VARCHAR NOT NULL,   -- e.g. 'open_meteo_archive'
    location_id VARCHAR NOT NULL,   -- usually a route id
    metric      VARCHAR NOT NULL,   -- e.g. 'temperature_2m'
    ts          TIMESTAMP NOT NULL, -- local (route timezone) wall-clock time
    value       DOUBLE,
    PRIMARY KEY (source, location_id, metric, ts)
);

CREATE TABLE IF NOT EXISTS departures (
    station_id     VARCHAR NOT NULL,
    line_id        VARCHAR NOT NULL,
    trip_code      BIGINT  NOT NULL,
    planned_utc    TIMESTAMP NOT NULL,
    label          VARCHAR,
    transport_type VARCHAR,
    destination    VARCHAR,
    platform       VARCHAR,
    realtime       BOOLEAN,
    delay_min      INTEGER,
    realtime_utc   TIMESTAMP,
    cancelled      BOOLEAN,
    sev            BOOLEAN,           -- Schienenersatzverkehr (replacement bus)
    infos          VARCHAR,           -- JSON list of incident messages
    first_seen_utc TIMESTAMP,
    last_seen_utc  TIMESTAMP,
    n_obs          INTEGER,
    PRIMARY KEY (station_id, line_id, trip_code, planned_utc)
);

CREATE TABLE IF NOT EXISTS collector_runs (
    ts_utc       TIMESTAMP,
    station_id   VARCHAR,
    n_departures INTEGER,
    ok           BOOLEAN,
    error        VARCHAR
);
"""


def db_path() -> Path:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    return config.DATA_DIR / "commuter.duckdb"


@contextlib.contextmanager
def connect(read_only: bool = False, retries: int = 40, wait: float = 0.25) -> Iterator[duckdb.DuckDBPyConnection]:
    path = db_path()
    if read_only and not path.exists():
        read_only = False  # first ever run: create the file and schema
    last_err: Exception | None = None
    for _ in range(retries):
        try:
            con = duckdb.connect(str(path), read_only=read_only)
            break
        except duckdb.IOException as e:  # file locked by another process
            last_err = e
            time.sleep(wait)
    else:
        raise RuntimeError(f"Could not open {path}: {last_err}")
    try:
        if not read_only:
            con.execute(SCHEMA)
        yield con
    finally:
        con.close()


def upsert_observations(df: pd.DataFrame) -> int:
    """df columns: source, location_id, metric, ts, value."""
    if df.empty:
        return 0
    df = df[["source", "location_id", "metric", "ts", "value"]]
    with connect() as con:
        con.register("incoming", df)
        con.execute("INSERT OR REPLACE INTO observations SELECT * FROM incoming")
    return len(df)


def query_df(sql: str, params: list | None = None) -> pd.DataFrame:
    with connect(read_only=True) as con:
        try:
            return con.execute(sql, params or []).df()
        except duckdb.CatalogException:
            return pd.DataFrame()  # tables not created yet
