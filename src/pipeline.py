"""
DhuanAlert Master Pipeline
Coordinates Layer 1 (Predictive Physics Engine) and Layer 2 (Policy-Constrained GenAI Advisory)
to deliver the combined FrontendPayload.
"""

from typing import List, Optional
from datetime import datetime
from src.types import (
    Hotspot,
    WeatherObservation,
    School,
    FrontendPayload,
    PredictiveOutput,
    AdvisoryOutput,
)
from src.config import Config, DEFAULT_CONFIG
from src.layer1_predictive.pipeline import Layer1PredictivePipeline
from src.layer2_generative.pipeline import Layer2GenerativePipeline


class DhuanAlertPipeline:
    """
    Unified end-to-end pipeline combining Predictive & Generative layers.
    """

    def __init__(self, config: Config = None):
        self.config = config or DEFAULT_CONFIG
        self.layer1 = Layer1PredictivePipeline(config=self.config)
        self.layer2 = Layer2GenerativePipeline()

    def run(
        self,
        hotspots: List[Hotspot],
        weather: List[WeatherObservation],
        schools: List[School],
        grap_stage: int = 3,
        human_approved: bool = True,
        run_timestamp: Optional[datetime] = None,
    ) -> FrontendPayload:
        """
        Executes both layers sequentially and produces the complete frontend contract.
        """
        # Step 1: Execute Layer 1 (Predictive / Physics)
        prediction: PredictiveOutput = self.layer1.run(
            hotspots=hotspots,
            weather=weather,
            schools=schools,
            run_timestamp=run_timestamp,
        )

        # Step 2: Execute Layer 2 (Generative AI / Policy-Gated Advisory)
        advisory: AdvisoryOutput = self.layer2.run(
            prediction=prediction,
            grap_stage=grap_stage,
            human_approved=human_approved,
        )

        return FrontendPayload(
            prediction=prediction,
            advisory=advisory,
        )
