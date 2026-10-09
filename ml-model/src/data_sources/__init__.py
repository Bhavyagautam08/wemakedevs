"""
Data Sources Package Interface
Unified entrypoint for NASA FIRMS, Open-Meteo, OpenAQ, and OSM School Datasets.
"""

from src.data_sources.nasa_firms import NasaFirmsClient
from src.data_sources.open_meteo import OpenMeteoClient
from src.data_sources.openaq_waqi import OpenAqWaqiClient
from src.data_sources.osm_schools import OsmSchoolClient

__all__ = [
    "NasaFirmsClient",
    "OpenMeteoClient",
    "OpenAqWaqiClient",
    "OsmSchoolClient",
]
