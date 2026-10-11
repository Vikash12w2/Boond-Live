import importlib.util
import io
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("fetch_weather", ROOT / "tools" / "fetch_weather.py")
fetch_weather = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_weather)


def fake_open_meteo(monkeypatch, daily):
    payload = {"latitude": 30.9, "longitude": 75.85, "daily": daily}

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        fetch_weather.urllib.request, "urlopen",
        lambda url, timeout: Response(json.dumps(payload).encode())
    )


def daily(et0, rain, tmax, prob=None):
    data = {
        "time": ["2021-11-01", "2021-11-02"],
        "et0_fao_evapotranspiration": et0,
        "precipitation_sum": rain,
        "temperature_2m_max": tmax,
    }
    if prob is not None:
        data["precipitation_probability_max"] = prob
    return data


def test_missing_et0_stops_the_download(monkeypatch):
    fake_open_meteo(monkeypatch, daily([2.0, None], [0, 0], [25, 25]))

    with pytest.raises(ValueError, match="ET0 missing"):
        fetch_weather.fetch(30.9, 75.85, "2021-11-01", "2021-11-02")


def test_missing_rain_is_zero_with_warning(monkeypatch, capsys):
    fake_open_meteo(monkeypatch, daily([2.0, 2.1], [None, 3.0], [25, None]))

    result = fetch_weather.fetch(30.9, 75.85, "2021-11-01", "2021-11-02")

    assert result["daily"]["rain_mm"] == [0.0, 3.0]
    assert result["daily"]["tmax_c"] == [25, None]
    assert result["missing_rain_dates"] == ["2021-11-01"]
    assert "WARNING" in capsys.readouterr().err


def test_historical_forecast_keeps_rain_probability(monkeypatch):
    fake_open_meteo(monkeypatch, daily([2.0, 2.1], [0, 5], [25, 26], prob=[10, None]))

    result = fetch_weather.fetch(30.9, 75.85, "2021-11-01", "2021-11-02", "historical-forecast")

    assert result["daily"]["rain_prob"] == [0.1, None]
