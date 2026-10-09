"""
CAQM GRAP (Graded Response Action Plan) Policy Definitions
Encodes the statutory CAQM schedule revised on 21.11.2025.
Defines allowed and prohibited actions for school operations across Stages I to IV.
"""

from typing import Dict, List, Any
from pydantic import BaseModel


class GrapStageDefinition(BaseModel):
    stage_number: int
    stage_name: str
    aqi_range: str
    statutory_basis: str
    allowed_school_actions: List[Dict[str, str]]
    prohibited_school_actions: List[str]


# Statutory CAQM GRAP Schedule (Revision 21.11.2025)
GRAP_SCHEDULE: Dict[int, GrapStageDefinition] = {
    1: GrapStageDefinition(
        stage_number=1,
        stage_name="Stage I - Poor",
        aqi_range="201 - 300",
        statutory_basis="CAQM Order Schedule Item 1-12",
        allowed_school_actions=[
            {
                "action_id": "advisory_awareness",
                "en": "Issue general health awareness advisory on mitigating outdoor dust exposure.",
                "hi": "धूल और वायु प्रदूषण से बचाव के लिए सामान्य स्वास्थ्य जागरूकता परामर्श जारी करें।",
                "clause": "General Citizen Charter",
            }
        ],
        prohibited_school_actions=[
            "No school closures permitted",
            "No suspension of physical classes",
            "No mandatory online classes",
        ],
    ),
    2: GrapStageDefinition(
        stage_number=2,
        stage_name="Stage II - Very Poor",
        aqi_range="301 - 400",
        statutory_basis="CAQM Order Schedule Item 1-14",
        allowed_school_actions=[
            {
                "action_id": "restrict_outdoor_assemblies",
                "en": "Restrict morning outdoor assemblies, sports periods, and unpaved playground activities.",
                "hi": "सुबह की बाहरी प्रार्थना सभाओं, खेल गतिविधियों और मैदान में होने वाले कार्यक्रमों को सीमित करें।",
                "clause": "Stage II Citizen & Operational Advice",
            }
        ],
        prohibited_school_actions=[
            "No full or partial class closures permitted under Stage II",
            "No evacuation orders",
        ],
    ),
    3: GrapStageDefinition(
        stage_number=3,
        stage_name="Stage III - Severe",
        aqi_range="401 - 450",
        statutory_basis="CAQM Order Schedule Revision 21.11.2025 Item 7",
        allowed_school_actions=[
            {
                "action_id": "discontinue_primary_physical_classes",
                "en": "Discontinue in-person physical classes for children up to Class V in NCT of Delhi and districts of Gurugram, Faridabad, Ghaziabad, and Gautam Buddh Nagar; transition to online/hybrid mode.",
                "hi": "राष्ट्रीय राजधानी क्षेत्र (NCT) दिल्ली तथा गुरुग्राम, फरीदाबाद, गाजियाबाद और गौतमबुद्ध नगर में कक्षा 5 तक के बच्चों के लिए प्रत्यक्ष कक्षाएं स्थगित कर हाइब्रिड/ऑनलाइन माध्यम में संचालित करें।",
                "clause": "Stage III Item 7",
            },
            {
                "action_id": "suspend_all_outdoor_sports",
                "en": "Completely suspend all outdoor sports, assemblies, and inter-school athletic events.",
                "hi": "सभी बाहरी खेल, प्रार्थना सभाएं और अंतर-विद्यालय खेल प्रतियोगिताएं पूर्णतः स्थगित करें।",
                "clause": "Stage III Operational Protocol",
            },
        ],
        prohibited_school_actions=[
            "Do not order physical closure of Classes VI to XII under Stage III (requires Stage IV)",
            "Do not declare general civil curfew or evacuation",
        ],
    ),
    4: GrapStageDefinition(
        stage_number=4,
        stage_name="Stage IV - Severe+",
        aqi_range="> 450",
        statutory_basis="CAQM Order Schedule Revision 21.11.2025 Item 4 & 5",
        allowed_school_actions=[
            {
                "action_id": "discontinue_classes_up_to_class_ix_and_xi",
                "en": "Discontinue in-person physical classes for Classes VI to IX and Class XI; conduct classes in online/hybrid mode (except Class X and XII appearing for board exams).",
                "hi": "कक्षा 6 से 9 और कक्षा 11 के लिए प्रत्यक्ष कक्षाएं स्थगित कर ऑनलाइन माध्यम अपनाएं (बोर्ड परीक्षा कक्षा 10 और 12 को छोड़कर)।",
                "clause": "Stage IV Item 4",
            },
            {
                "action_id": "consider_college_suspension",
                "en": "Competent state authorities may consider discontinuing physical classes for colleges and higher educational institutions.",
                "hi": "सक्षम प्राधिकारी कॉलेजों और उच्च शिक्षण संस्थानों में प्रत्यक्ष कक्षाएं स्थगित करने पर विचार कर सकते हैं।",
                "clause": "Stage IV Item 5",
            },
        ],
        prohibited_school_actions=[
            "Do not suspend emergency public utility services",
            "Do not alter board exam schedules without CBSE/State Board order",
        ],
    ),
}
