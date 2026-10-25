"""Local project planning estimates and architectural prompt generation."""

from typing import Dict


_CONSTRUCTION_RATE = {
    "Residential": 2100,
    "Commercial": 2800,
    "Industrial": 1900,
    "Institutional": 2500,
}

# Indicative completed built-up property benchmark in INR per square foot.
_MARKET_RATE = {
    "Residential": {"Tier 1": 12500, "Tier 2": 7800, "Tier 3": 5200},
    "Commercial": {"Tier 1": 18500, "Tier 2": 11500, "Tier 3": 7600},
    "Industrial": {"Tier 1": 7200, "Tier 2": 5000, "Tier 3": 3600},
    "Institutional": {"Tier 1": 9800, "Tier 2": 6800, "Tier 3": 4700},
}

_CITY_COST_FACTOR = {"Tier 1": 1.22, "Tier 2": 1.0, "Tier 3": 0.86}
_MATERIAL_INTENSITY = {
    "Residential": {"steel_kg_per_sqft": 3.8, "cement_bags_per_sqft": 0.40},
    "Commercial": {"steel_kg_per_sqft": 4.6, "cement_bags_per_sqft": 0.46},
    "Industrial": {"steel_kg_per_sqft": 3.2, "cement_bags_per_sqft": 0.34},
    "Institutional": {"steel_kg_per_sqft": 4.2, "cement_bags_per_sqft": 0.43},
}


def estimate_project(structure: str, area_sqft: float, tier: str, completion_percent: int) -> Dict[str, object]:
    """Return a transparent, preliminary estimate from fixed benchmark assumptions."""
    if structure not in _CONSTRUCTION_RATE:
        raise ValueError("Choose a supported structure type.")
    if tier not in _CITY_COST_FACTOR:
        raise ValueError("Choose Tier 1, Tier 2 or Tier 3.")
    area = max(0.0, float(area_sqft))
    progress = max(0, min(100, int(completion_percent))) / 100.0
    budget = area * _CONSTRUCTION_RATE[structure] * _CITY_COST_FACTOR[tier]
    completed_asset_value = area * _MARKET_RATE[structure][tier]
    # The estimator treats the asset value as the completed built-up benchmark,
    # then prorates it by physical completion. Land value is excluded.
    current_asset_value = completed_asset_value * progress
    intensity = _MATERIAL_INTENSITY[structure]
    steel = area * intensity["steel_kg_per_sqft"]
    cement = area * intensity["cement_bags_per_sqft"]
    incurred = budget * progress
    return {
        "project_budget_inr": round(budget),
        "capex_incurred_inr": round(incurred),
        "budget_remaining_inr": round(max(0, budget - incurred)),
        "asset_value_inr": round(current_asset_value),
        "asset_value_on_completion_inr": round(completed_asset_value),
        "steel_kg": round(steel),
        "steel_tonnes": round(steel / 1000, 1),
        "cement_bags": round(cement),
        "assumptions": (
            "Illustrative planning benchmarks only: construction rates are ₹/sq ft by structure type "
            "and location tier; capex is assumed to track physical completion. Steel and cement are "
            "gross rule-of-thumb quantities before design, wastage or procurement adjustments. Asset "
            "value uses a completed built-up property benchmark, prorated by completion; land, taxes, "
            "financing, approvals, location-specific comparables and market movement are excluded. "
            "Replace these inputs with a local QS estimate, drawings, BOQ and current comparable sales."
        ),
    }


def format_inr(amount: float) -> str:
    """Format INR amounts in crores or lakhs for compact display."""
    value = max(0.0, float(amount))
    if value >= 10_000_000:
        return "₹ " + format(value / 10_000_000, ",.2f") + " Cr"
    if value >= 100_000:
        return "₹ " + format(value / 100_000, ",.2f") + " L"
    return "₹ " + format(value, ",.0f")


def rendering_prompt(structure: str, area_sqft: float, tier: str) -> str:
    """Create a descriptive prompt for the optional Pollinations concept render."""
    style = {
        "Residential": "contemporary climate-responsive Indian residence",
        "Commercial": "modern mixed-use commercial building with an active street frontage",
        "Industrial": "efficient light-industrial facility with clear-span bays and safe circulation",
        "Institutional": "welcoming institutional campus building with shaded gathering areas",
    }.get(structure, "contemporary Indian building")
    return (
        "Conceptual architectural visualization, " + style + ", approximately " + format(float(area_sqft), ",.0f")
        + " square feet built-up, located in an Indian " + tier.lower() + " city. Show a believable massing and facade, "
        "durable locally appropriate materials, daylight, landscaped context, human-scale entry, realistic construction "
        "proportions, clean professional architectural render, wide three-quarter view. No text, no labels, no watermark. "
        "Illustrative concept only, not a construction drawing."
    )
