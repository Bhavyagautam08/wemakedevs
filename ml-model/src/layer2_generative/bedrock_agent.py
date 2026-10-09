"""
Amazon Bedrock Advisory Agent Connector
Constructs structured, grounded prompts from Layer 1 prediction payloads and official
CAQM GRAP legal policy context, generating bilingual (English and Hindi) operational advisories.
Includes offline fallback mode for local testing without AWS credentials.
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from src.types import BilingualText, RecommendedAction
from src.config import DEFAULT_CONFIG


class BedrockAdvisoryAgent:
    """
    Connects to Amazon Bedrock (Amazon Nova / Titan / Claude) or provides
    a deterministic high-fidelity mock if running offline.
    """

    def __init__(self, model_id: str = None, region: str = None, offline_mode: bool = None):
        self.model_id = model_id or DEFAULT_CONFIG.bedrock_model_id
        self.region = region or DEFAULT_CONFIG.bedrock_region
        self.offline_mode = offline_mode if offline_mode is not None else DEFAULT_CONFIG.offline_fallback_mode

        # Initialize Boto3 client only if online
        self._bedrock_client = None
        if not self.offline_mode:
            try:
                self._bedrock_client = boto3.client("bedrock-runtime", region_name=self.region)
            except Exception:
                self.offline_mode = True

    def build_grounded_prompt(self, context_payload: Dict[str, Any]) -> str:
        """
        Builds the strict, grounded system prompt injecting all verified variables.
        """
        return f"""You are the official Environmental Safety Communication Officer for Delhi-NCR Disaster Management.
You synthesize operational school advisories grounded strictly in the provided prediction state and CAQM GRAP legal regulations.

CRITICAL INSTRUCTIONS:
1. Ground every statement strictly in the provided Context Object below.
2. DO NOT invent numerical sensor data or exact AQI figures (use the provided smoke corridor index and arrival hours).
3. DO NOT order full school closures unless specifically authorized under the current GRAP stage.
4. DO NOT issue medical prescriptions or evacuation directives.
5. Generate identical semantic instructions in English and official Hindi (Devanagari).

CONTEXT OBJECT:
{json.dumps(context_payload, indent=2)}

Output valid JSON matching this schema:
{{
  "headline_en": "...",
  "headline_hi": "...",
  "summary_en": "...",
  "summary_hi": "...",
  "recommended_actions": [
    {{
      "action_id": "...",
      "en": "...",
      "hi": "...",
      "policy_basis": "..."
    }}
  ]
}}
"""

    def generate_advisory(self, grounded_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes generative synthesis via Amazon Bedrock with offline mock fallback.
        """
        if self.offline_mode or self._bedrock_client is None:
            return self._generate_offline_mock(grounded_context)

        prompt = self.build_grounded_prompt(grounded_context)

        try:
            # Amazon Nova / Titan invocation payload
            body = json.dumps({
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"max_new_tokens": 1000, "temperature": 0.2},
            })

            response = self._bedrock_client.invoke_model(
                modelId=self.model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            resp_body = json.loads(response["body"].read().decode("utf-8"))
            raw_text = resp_body["output"]["message"]["content"][0]["text"]
            return json.loads(raw_text)

        except Exception as e:
            # Graceful degradation to offline template engine
            return self._generate_offline_mock(grounded_context)

    def _generate_offline_mock(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deterministic, legally grounded fallback synthesis adhering to CAQM GRAP.
        """
        pred = ctx.get("prediction", {})
        policy = ctx.get("policy_context", {})
        schools_count = ctx.get("affected_school_count", 0)
        zone_name = ctx.get("zone_name", "North West Delhi")
        lead_h = ctx.get("lead_hours", 3.0)
        grap_stage = policy.get("grap_stage", 3)

        if grap_stage >= 3:
            headline_en = f"Smoke Corridor Precautionary Advisory: {zone_name}"
            headline_hi = f"धुआं कॉरिडोर सुरक्षा परामर्श: {zone_name}"
            summary_en = (
                f"Lagrangian transport models project stubble smoke arrival in {zone_name} "
                f"within {lead_h} hours. Under CAQM GRAP Stage III (Item 7), physical classes "
                f"for Nursery to Class V in the affected {schools_count} schools should transition to online/hybrid mode."
            )
            summary_hi = (
                f"लाग्रेंजियन मॉडल के अनुसार {zone_name} में अगले {lead_h} घंटों के भीतर पराली के धुएं का प्रभाव संभावित है। "
                f"CAQM ग्रैप (GRAP) चरण-III (मद 7) के तहत प्रभावित {schools_count} विद्यालयों में कक्षा 5 तक प्रत्यक्ष कक्षाएं स्थगित कर "
                f"हाइब्रिड/ऑनलाइन माध्यम अपनाने का परामर्श दिया जाता है।"
            )
            actions = [
                {
                    "action_id": "discontinue_primary_physical_classes",
                    "en": "Transition Nursery to Class V to online/hybrid learning; suspend in-person attendance.",
                    "hi": "नर्सरी से कक्षा 5 तक प्रत्यक्ष कक्षाएं स्थगित कर ऑनलाइन/हाइब्रिड माध्यम संचालित करें।",
                    "policy_basis": "CAQM_GRAP_Stage_III_Item_7",
                },
                {
                    "action_id": "suspend_all_outdoor_sports",
                    "en": "Cancel all morning assemblies, outdoor physical education, and athletic practices.",
                    "hi": "सुबह की सभी प्रार्थना सभाएं, बाहरी खेलकूद और शारीरिक शिक्षा सत्र रद्द करें।",
                    "policy_basis": "CAQM_GRAP_Stage_III_Item_7",
                },
            ]
        else:
            headline_en = f"Air Quality Precautionary Alert: {zone_name}"
            headline_hi = f"वायु गुणवत्ता एहतियाती अलर्ट: {zone_name}"
            summary_en = (
                f"Smoke corridor movement detected towards {zone_name} with estimated arrival in {lead_h} hours. "
                f"Authorities are advised to restrict outdoor school assemblies under GRAP Stage II."
            )
            summary_hi = (
                f"{zone_name} की ओर धुएं के फैलाव का अनुमान है। ग्रैप चरण-II के अंतर्गत स्कूलों में बाहरी प्रार्थना सभाओं को सीमित करने का परामर्श है।"
            )
            actions = [
                {
                    "action_id": "restrict_outdoor_assemblies",
                    "en": "Keep morning assembly indoors and avoid prolonged outdoor physical exertion.",
                    "hi": "सुबह की प्रार्थना सभा इनडोर आयोजित करें और भारी शारीरिक गतिविधियों से बचें।",
                    "policy_basis": "CAQM_GRAP_Stage_II_Item_3",
                }
            ]

        return {
            "headline_en": headline_en,
            "headline_hi": headline_hi,
            "summary_en": summary_en,
            "summary_hi": summary_hi,
            "recommended_actions": actions,
        }
