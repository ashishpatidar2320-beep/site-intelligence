"""Gemini-backed multimodal analysis with explicitly labelled demo fallbacks."""

import io
import json
import re
from typing import Any, Dict, List, Optional

from PIL import Image


DEFAULT_MODEL = "gemini-3.8-flash"
LIMITATIONS = (
    "Visual screening only. Camera angle, occlusion, lighting and image quality limit detection. "
    "This output is not a compliance certification, structural diagnosis or substitute for an onsite inspection."
)


def _prepare_image(image_bytes: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    image.thumbnail((1600, 1600))
    return image


def _gemini_json(prompt: str, image_bytes: bytes, api_key: str, model: str) -> Dict[str, Any]:
    if not api_key:
        raise ValueError("A Gemini API key is required for live image analysis.")
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=[prompt, _prepare_image(image_bytes)],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
            max_output_tokens=1800,
        ),
    )
    text = response.text
    if not text:
        raise ValueError("Gemini returned an empty response.")
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text, flags=re.IGNORECASE)
    result = json.loads(cleaned)
    if not isinstance(result, dict):
        raise ValueError("Gemini returned JSON in an unexpected format.")
    return result


def _to_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(maximum, int(float(value))))
    except (TypeError, ValueError, OverflowError):
        return default


def _list_of_strings(value: Any, default: Optional[List[str]] = None) -> List[str]:
    if not isinstance(value, list):
        return list(default or [])
    return [str(item).strip() for item in value if str(item).strip()]


def analyze_safety_image(image_bytes: bytes, mime_type: str, api_key: str, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    """Analyze a site image and normalize the result to the safety report contract."""
    prompt = """You are a cautious construction-site visual screening assistant. Analyze only what is visible in this photograph. Never infer compliance from an unseen detail; use 'Not visible' when uncertain. This is not a legal or engineering certification.

Review visible workers for hard hats/helmets, high-visibility vests, steel-toe safety boots and safety harnesses where the work context makes a harness appropriate. Note that a photo cannot verify steel toes, PPE certification, harness anchorage or fit. Identify visible hazards and practical corrective actions.

Use OSHA PPE concepts as a general reference lens. IS 456 is a concrete design code and is not a PPE standard; do not claim IS 456 establishes PPE compliance. Avoid definitive claims about legal compliance. Return only valid JSON using this schema:
{
  "safety_score": integer from 0 to 100,
  "overall_status": "Safe with observations" | "Action required" | "Immediate review required",
  "ppe_detection": {
    "helmets": {"status": "Compliant" | "Non-compliant" | "Not visible", "notes": string},
    "high_visibility_vests": {"status": "Compliant" | "Non-compliant" | "Not visible", "notes": string},
    "steel_toe_boots": {"status": "Compliant" | "Non-compliant" | "Not visible", "notes": string},
    "safety_harnesses": {"status": "Compliant" | "Non-compliant" | "Not visible", "notes": string}
  },
  "hazards": [{"hazard": string, "description": string, "severity": "Low" | "Medium" | "High" | "Critical", "remedy": string}],
  "limitations": string
}
Score only observable risk indicators. If no workers or hazards can be assessed, say so in notes and lower confidence through limitations."""
    raw = _gemini_json(prompt, image_bytes, api_key, model)
    ppe_raw = raw.get("ppe_detection", {})
    ppe_keys = {
        "helmets": "helmets",
        "high_visibility_vests": "high_visibility_vests",
        "steel_toe_boots": "steel_toe_boots",
        "safety_harnesses": "safety_harnesses",
    }
    ppe = {}
    for key in ppe_keys:
        item = ppe_raw.get(key, {}) if isinstance(ppe_raw, dict) else {}
        if isinstance(item, str):
            item = {"status": item, "notes": ""}
        if not isinstance(item, dict):
            item = {}
        status_value = str(item.get("status", "Not visible")).strip().lower()
        status = {
            "compliant": "Compliant",
            "non-compliant": "Non-compliant",
            "not visible": "Not visible",
        }.get(status_value, "Not visible")
        ppe[key] = {"status": status, "notes": str(item.get("notes", ""))}
    hazard_items = raw.get("hazards", [])
    hazards = []
    if isinstance(hazard_items, list):
        for item in hazard_items:
            if not isinstance(item, dict):
                continue
            severity = str(item.get("severity", "Medium")).title()
            if severity not in ("Low", "Medium", "High", "Critical"):
                severity = "Medium"
            hazards.append({
                "hazard": str(item.get("hazard", "Visible site condition")),
                "description": str(item.get("description", "")),
                "severity": severity,
                "remedy": str(item.get("remedy", "Have a competent supervisor review and correct the condition.")),
            })
    overall = str(raw.get("overall_status", "Action required"))
    if overall not in ("Safe with observations", "Action required", "Immediate review required"):
        overall = "Action required"
    return {
        "safety_score": _to_int(raw.get("safety_score"), 50, 0, 100),
        "overall_status": overall,
        "ppe_detection": ppe,
        "hazards": hazards,
        "limitations": str(raw.get("limitations", LIMITATIONS)),
        "analysis_mode": "gemini",
        "model": model,
        "image_mime_type": mime_type,
    }


def analyze_crack_image(image_bytes: bytes, mime_type: str, api_key: str, model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    """Classify a visible surface defect, with uncertainty and safe next steps."""
    prompt = """You are a cautious construction surface-defect screening assistant, not a structural engineer. Analyze only visible evidence. A photo without a scale cannot reliably measure crack width or determine depth, movement or cause. Never declare a structure safe.

Classify the most likely visible issue among Hairline, Settlement, Structural Shear, Thermal Expansion, Spalling, or Unclear. Give a rough width estimate in millimetres only if a visible scale makes that plausible; otherwise set estimated_width_mm to null. Explain likely causes as hypotheses and recommend inspection and repair options as guidance for engineer review. Escalate potentially structural patterns.

Return only valid JSON:
{
  "defect_type": "Hairline" | "Settlement" | "Structural Shear" | "Thermal Expansion" | "Spalling" | "Unclear",
  "estimated_width_mm": number or null,
  "root_causes": [string],
  "recommended_repairs": [string],
  "urgency": "Routine monitoring" | "Prompt engineering review" | "Urgent engineering review",
  "engineering_note": string
}
Mention that epoxy injection, grouting or other repairs require confirmation of crack activity, substrate and cause by a qualified engineer; do not prescribe a repair as certain based on the image."""
    raw = _gemini_json(prompt, image_bytes, api_key, model)
    allowed_types = ("Hairline", "Settlement", "Structural Shear", "Thermal Expansion", "Spalling", "Unclear")
    defect = str(raw.get("defect_type", "Unclear"))
    if defect not in allowed_types:
        defect = "Unclear"
    width = raw.get("estimated_width_mm")
    try:
        width = round(max(0, float(width)), 2) if width is not None else None
    except (TypeError, ValueError, OverflowError):
        width = None
    urgency = str(raw.get("urgency", "Prompt engineering review"))
    if urgency not in ("Routine monitoring", "Prompt engineering review", "Urgent engineering review"):
        urgency = "Prompt engineering review"
    return {
        "defect_type": defect,
        "estimated_width_mm": width,
        "root_causes": _list_of_strings(raw.get("root_causes")),
        "recommended_repairs": _list_of_strings(raw.get("recommended_repairs")),
        "urgency": urgency,
        "engineering_note": str(raw.get("engineering_note", "Photographic assessment is preliminary; consult a qualified structural engineer.")),
        "analysis_mode": "gemini",
        "model": model,
        "image_mime_type": mime_type,
    }


def answer_construction_question(question: str, history: List[Dict[str, str]], weather: str, api_key: str, model: str = DEFAULT_MODEL) -> str:
    """Answer a site-related chat question, with a useful local demo response."""
    if not api_key:
        return _demo_chat_answer(question, weather)
    from google import genai
    from google.genai import types

    transcript = []
    for item in history[-10:]:
        role = "User" if item.get("role") == "user" else "Assistant"
        transcript.append(role + ": " + str(item.get("content", "")))
    prompt = (
        "You are a practical construction engineering assistant. Give concise, actionable guidance for planning, concrete, materials, quality and site safety. "
        "Do not replace the responsible engineer, approved drawings, method statements or local rules. For safety-critical or structural issues, identify the need for qualified onsite review. "
        "Current weather condition: " + weather + ". Treat the conversation as follows:\n" + "\n".join(transcript) + "\nAssistant:"
    )
    response = genai.Client(api_key=api_key).models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.4, max_output_tokens=700),
    )
    if not response.text:
        raise ValueError("Gemini returned an empty response.")
    return response.text.strip()


def _demo_chat_answer(question: str, weather: str) -> str:
    q = question.lower()
    if weather == "High Wind":
        weather_note = "For today's high wind, check crane and work-at-height stop limits before starting and secure loose materials."
    elif weather == "Heavy Rain":
        weather_note = "With heavy rain, check temporary electrical protection, excavations, drainage and fresh concrete protection."
    elif weather == "Extreme Heat":
        weather_note = "In extreme heat, plan shaded breaks, hydration, heat illness monitoring and concrete moisture protection."
    else:
        weather_note = "Keep the daily toolbox talk and routine access, edge-protection and PPE checks in place."
    if any(term in q for term in ("concrete", "curing", "cement")):
        answer = "For concrete work, follow the approved mix, placement and curing method; record weather, batch and placement details. Ask the engineer to review any unexpected cracking or honeycombing."
    elif any(term in q for term in ("crack", "structural", "beam", "column", "foundation")):
        answer = "Document the location, pattern and change over time, and keep a scale in photographs. A qualified structural engineer should assess the member before selecting a repair."
    elif any(term in q for term in ("ppe", "safety", "hazard", "crane", "scaffold")):
        answer = "Pause the task if there is an immediate danger, secure the area and notify the site supervisor. Use the approved risk assessment and equipment-specific limits."
    else:
        answer = "Break the task into scope, resources, quality checks and hold points. Confirm the latest approved drawings and method statement with the responsible site team."
    return answer + "\n\n" + weather_note + "\n\n*Demo assistant: connect Gemini for conversational model responses.*"


def demo_safety_report() -> Dict[str, Any]:
    return {
        "safety_score": 72,
        "overall_status": "Action required",
        "ppe_detection": {
            "helmets": {"status": "Not visible", "notes": "Demo placeholder; no image assessment was performed."},
            "high_visibility_vests": {"status": "Not visible", "notes": "Demo placeholder; no image assessment was performed."},
            "steel_toe_boots": {"status": "Not visible", "notes": "Cannot be verified from most photos."},
            "safety_harnesses": {"status": "Not visible", "notes": "Demo placeholder; no image assessment was performed."},
        },
        "hazards": [{
            "hazard": "Example hazard for demonstration",
            "description": "Replace this placeholder with a live Gemini image audit.",
            "severity": "Medium",
            "remedy": "Review the site in person and follow the approved task risk assessment.",
        }],
        "limitations": "Demonstration output only; it does not describe the uploaded image.",
        "analysis_mode": "demo",
    }


def demo_crack_report() -> Dict[str, Any]:
    return {
        "defect_type": "Unclear",
        "estimated_width_mm": None,
        "root_causes": ["Placeholder only; no image assessment was performed."],
        "recommended_repairs": ["Obtain a close-up with a scale and request qualified engineering review."],
        "urgency": "Prompt engineering review",
        "engineering_note": "Demonstration output only; this is not a diagnosis of the uploaded surface.",
        "analysis_mode": "demo",
    }
