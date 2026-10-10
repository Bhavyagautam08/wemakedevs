import io
from unittest.mock import patch

import pytest

from src.data_sources.nasa_firms import DEFAULT_NW_CORRIDOR_BBOX, NasaFirmsClient
from src.data_sources.open_meteo import OpenMeteoClient


def test_nasa_firms_parses_actual_csv_columns():
    csv_text = (
        "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,"
        "instrument,confidence,version,bright_ti5,frp,daynight\n"
        "30.1,76.2,330.7,0.4,0.5,2026-10-09,741,N,VIIRS,n,2.0,290.0,12.4,N\n"
    )

    [fire] = NasaFirmsClient()._parse_csv_response(csv_text)

    assert fire.latitude == 30.1
    assert fire.longitude == 76.2
    assert fire.frp == 12.4
    assert fire.confidence_class == "n"
    assert fire.acq_timestamp.isoformat() == "2026-10-09T07:41:00+00:00"


def test_nasa_firms_empty_live_response_stays_empty():
    csv_text = (
        "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,"
        "instrument,confidence,version,bright_ti5,frp,daynight\n"
    )
    client = NasaFirmsClient(map_key="configured-test-key")
    response = io.BytesIO(csv_text.encode())

    with patch("src.data_sources.nasa_firms.urllib.request.urlopen", return_value=response):
        assert client.fetch_active_fires() == []


def test_nasa_firms_requests_northwest_corridor_bbox_by_default():
    header = (
        "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,"
        "instrument,confidence,version,bright_ti5,frp,daynight\n"
    )
    client = NasaFirmsClient(map_key="configured-test-key")

    with patch("src.data_sources.nasa_firms.urllib.request.urlopen", return_value=io.BytesIO(header.encode())) as request:
        assert client.fetch_active_fires() == []

    assert f"VIIRS_SNPP_NRT/{DEFAULT_NW_CORRIDOR_BBOX}/1" in request.call_args.args[0].full_url


def test_nasa_firms_requires_live_api_key():
    with pytest.raises(RuntimeError, match="NASA_FIRMS_MAP_KEY is required"):
        NasaFirmsClient(map_key="MOCK").fetch_active_fires()


def test_open_meteo_parses_actual_hourly_response():
    response = {
        "hourly": {
            "time": ["2026-10-09T19:00"],
            "wind_speed_10m": [8.0],
            "wind_direction_10m": [310.0],
            "boundary_layer_height": [340.0],
            "temperature_2m": [23.5],
            "relative_humidity_2m": [55.0],
        }
    }

    [weather] = OpenMeteoClient()._parse_response(response)

    assert weather.forecast_timestamp.isoformat() == "2026-10-09T19:00:00+00:00"
    assert weather.wind_speed_mps == pytest.approx(8.0 / 3.6, abs=0.01)
    assert weather.wind_direction_deg == 310.0


def test_open_meteo_requires_an_explicit_weather_location():
    with pytest.raises(ValueError, match="WEATHER_LOCATION_REQUIRED"):
        OpenMeteoClient().fetch_forecast()


def test_open_meteo_rejects_inconsistent_hourly_response_arrays():
    response = {
        "hourly": {
            "time": ["2026-10-09T19:00", "2026-10-09T20:00"],
            "wind_speed_10m": [8.0],
            "wind_direction_10m": [310.0, 310.0],
            "boundary_layer_height": [340.0, 340.0],
            "temperature_2m": [23.5, 23.5],
            "relative_humidity_2m": [55.0, 55.0],
        }
    }

    with pytest.raises(ValueError, match="OPEN_METEO_SCHEMA_ERROR"):
        OpenMeteoClient()._parse_response(response)
