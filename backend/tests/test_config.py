import datetime as dt


def test_example_config_parses(settings):
    r = settings.route()
    assert r.period_start == dt.date(2027, 1, 10)
    assert r.out_time == dt.time(8, 0)
    # 10 Jan 2027 (Sun) .. 21 Mar 2027 (Sun) = exactly 10 working weeks
    assert len(r.commute_days()) == 50
    assert settings.collector.windows[0] == (dt.time(6), dt.time(10))
