import datetime as dt
from dataclasses import replace

import numpy as np
import pandas as pd

from app.analysis import climatology
from app.analysis.climatology import build_legs, calendar, leg_hours, summarize


def test_leg_hours():
    # 08:00-08:30: precipitation stamped 09:00 covers 08:00-09:00
    assert leg_hours(dt.time(8, 0), 30) == ([9], [8, 9])
    # 17:30-18:00: only the 18:00 stamp (17:00-18:00) overlaps
    assert leg_hours(dt.time(17, 30), 30) == ([18], [17, 18])


def synthetic_weather(years, start_md=(1, 10), days=71) -> pd.DataFrame:
    """Mild, dry, calm weather everywhere - except it pours at 09:00 on the first day of each year."""
    idx = []
    for y in years:
        s = pd.Timestamp(y, *start_md)
        idx.append(pd.date_range(s, s + pd.Timedelta(days=days), freq="h", inclusive="left"))
    idx = idx[0].append(idx[1:]) if len(idx) > 1 else idx[0]
    w = pd.DataFrame(index=idx)
    w["temperature_2m"] = 5.0
    w["apparent_temperature"] = 3.0
    w["precipitation"] = 0.0
    w["snowfall"] = 0.0
    w["snow_depth"] = 0.0
    w["wind_gusts_10m"] = 20.0
    for y in years:
        w.loc[pd.Timestamp(y, *start_md, 9), "precipitation"] = 3.0
    return w


def test_build_legs_flags_wet_morning(settings):
    s = replace(settings, first_year=2020, last_year=2022)
    r = s.route()
    legs = build_legs(synthetic_weather([2020, 2021, 2022]), r, s, s.thresholds)
    first = legs[(legs["stay_date"] == r.period_start)]
    assert set(first["leg"]) == {"out", "back"}
    assert not first.loc[first["leg"] == "out", "cyclable"].any()   # rained 08-09
    assert first.loc[first["leg"] == "back", "cyclable"].all()
    # every other leg is cyclable in this dream climate
    assert legs["cyclable"].sum() == len(legs) - 3


def test_thresholds_change_outcome(settings):
    s = replace(settings, first_year=2021, last_year=2021)
    r = s.route()
    w = synthetic_weather([2021])
    strict = replace(s.thresholds, min_temp_c=4.0)  # feels-like is 3 °C -> too cold
    assert not build_legs(w, r, s, strict)["cyclable"].any()


def test_summary_and_calendar(settings):
    s = replace(settings, first_year=2020, last_year=2022)
    r = s.route()
    legs = build_legs(synthetic_weather([2020, 2021, 2022]), r, s, s.thresholds)
    out = summarize(legs, r, s, s.thresholds)
    assert out["has_data"] and out["years"]["n"] == 3
    assert out["legs"]["back"]["cyclable"] == 100.0
    assert out["days"]["expected_both_days"]["median"] >= 49
    cal = calendar(legs, r)
    assert len(cal["years"]) == 3 and len(cal["dates"]) == 71
    assert cal["values"][0][0] is None  # 10 Jan 2027 is a Sunday


def test_empty_store_is_graceful(settings):
    r = settings.route()
    assert climatology.load_weather(r.id).empty
    out = summarize(pd.DataFrame(), r, settings, settings.thresholds)
    assert out["has_data"] is False
