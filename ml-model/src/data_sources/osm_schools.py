"""
OpenStreetMap / Verified Geodata Ingestion Module for NCR School Clusters
Provides geolocations, student capacity proxies, and district mappings.
"""

import os
import json
import logging
from typing import List
from src.types import School

logger = logging.getLogger("dhuanalert.schools")


class OsmSchoolClient:
    """
    Manages verified Delhi-NCR school geographic cluster datasets.
    """

    @staticmethod
    def load_ncr_schools() -> List[School]:
        """Loads verified OpenStreetMap school locations for Delhi, Gurugram, Faridabad, Noida, and Ghaziabad."""
        data_path = os.path.join(os.path.dirname(__file__), "..", "data", "ncr_schools.json")
        if not os.path.exists(data_path):
            logger.warning(f"Schools file not found at {data_path}")
            return []

        with open(data_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        return [School(**s) for s in raw]
