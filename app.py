"""Multimodal Construction Intelligence Platform — Streamlit application."""

import json
import os
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import streamlit as st

from construction_ai import (
    DEFAULT_MODEL,
    analyze_crack_image,
    analyze_safety_image,
    answer_construction_question,
    demo_crack_report,
    demo_safety_report,
)
from planning import estimate_project, format_inr, rendering_prompt


st.set_page_config(
    page_title="Multimodal Construction Intelligence Platform",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

FEATURES = [
    "Site Safety & PPE Audit",
    "Crack Diagnostics",
    "Planning & Valuation",
    "Daily Assistant & Weather",
]


def _select_tab_from_sidebar():
    st.session_state["active_module_tab"] = st.session_state["feature_navigation"]


def _select_sidebar_from_tab():
    st.session_state["feature_navigation"] = st.session_state["active_module_tab"]


_streamlit_version = tuple(int(part) for part in st.__version__.split(".")[:2])
_has_stateful_tabs = _streamlit_version >= (1, 55)


st.markdown(
    """
    <style>
    :root { --ink:#142a31; --muted:#61777a; --teal:#087f78; --lime:#c7e75b; --paper:#f5f7f4; }
    html, body, [class*="css"] { font-family:Arial, sans-serif; }
    .stApp { background:var(--paper); }
    h1,h2,h3 { font-family:Arial, sans-serif !important; color:var(--ink); }
    .hero { padding:1.35rem 1.6rem; border-radius:18px; background:linear-gradient(115deg,#12383a,#087f78); color:white; margin-bottom:1rem; }
    .hero h1 { color:white !important; margin:0; font-size:2rem; }
    .hero p { color:#d8eeea; margin:.35rem 0 0 0; }
    .eyebrow { color:#bfe56b; text-transform:uppercase; letter-spacing:.14em; font-size:.72rem; font-weight:700; }
    .panel { padding:1rem 1.15rem; background:white; border:1px solid #e1e9e5; border-radius:14px; margin:.25rem 0 .8rem; }
    .small-muted { color:var(--muted); font-size:.88rem; }
    .pill { display:inline-block; padding:.22rem .7rem; border-radius:999px; background:#e5f4e9; color:#246b3d; font-weight:700; font-size:.8rem; }
    .pill-warn { background:#fff0d5; color:#8a5500; }
    .pill-danger { background:#fee8e5; color:#a83329; }
    div[data-testid="stMetric"] { background:white; border:1px solid #e1e9e5; border-radius:14px; padding:.8rem 1rem; }
    div[data-testid="stMetricLabel"] { color:var(--muted); }
    section[data-testid="stSidebar"] { background:#edf2ee; }
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2 { color:var(--ink); }
    .stButton button, .stDownloadButton button { border-radius:10px; font-weight:700; }
    .disclaimer { color:#647579; font-size:.78rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _secret_key(name):
    key = os.getenv(name, "")
    if key:
        return key
    try:
        return str(st.secrets.get(name, "") or "")
    except Exception:
        return ""


def _generate_pollinations_image(prompt, api_key):
    url = "https://gen.pollinations.ai/image/" + quote(prompt, safe="") + "?model=flux&width=1024&height=768"
    request = Request(url, headers={"Authorization": "Bearer " + api_key, "Accept": "image/*"})
    with urlopen(request, timeout=120) as response:
        content_type = response.headers.get("Content-Type", "")
        image_bytes = response.read(15 * 1024 * 1024 + 1)
    if len(image_bytes) > 15 * 1024 * 1024:
        raise ValueError("The generated image exceeded the 15 MB display limit.")
    if not content_type.lower().startswith("image/"):
        raise ValueError("Pollinations returned a non-image response. Check the key, model access and API status.")
    return image_bytes


def _report_bytes(data):
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


def _render_safety_report(report):
    mode = report.get("analysis_mode", "demo")
    if mode == "demo":
        st.warning("Demonstration output: this report was not produced by visual image analysis.")
    else:
        st.success("Gemini image analysis completed. Treat this as a screening aid and verify onsite.")

    score = report.get("safety_score", 0)
    status = report.get("overall_status", "Review required")
    metric_cols = st.columns(3)
    metric_cols[0].metric("Safety score", str(score) + "/100")
    metric_cols[1].metric("Overall status", status)
    metric_cols[2].metric("Hazards identified", len(report.get("hazards", [])))

    st.subheader("PPE checklist")
    checklist = report.get("ppe_detection", {})
    cols = st.columns(4)
    for col, (label, item) in zip(cols, checklist.items()):
        item = item if isinstance(item, dict) else {"status": str(item), "notes": ""}
        status_text = item.get("status", "Not visible")
        col.markdown(f"**{label.replace('_', ' ').title()}**")
        if status_text.lower() in ("compliant", "present"):
            col.markdown(f'<span class="pill">{status_text}</span>', unsafe_allow_html=True)
        elif status_text.lower() in ("non-compliant", "missing", "absent"):
            col.markdown(f'<span class="pill pill-danger">{status_text}</span>', unsafe_allow_html=True)
        else:
            col.markdown(f'<span class="pill pill-warn">{status_text}</span>', unsafe_allow_html=True)
        if item.get("notes"):
            col.caption(item["notes"])

    st.subheader("Site hazards and corrective actions")
    hazards = report.get("hazards", [])
    if not hazards:
        st.info("No hazards were returned. This does not confirm that the site is hazard-free.")
    for hazard in hazards:
        severity = hazard.get("severity", "Medium")
        st.markdown(
            f"**{hazard.get('hazard', 'Site condition')}** · {severity}  \n"
            f"{hazard.get('description', '')}  \n"
            f"*Corrective action:* {hazard.get('remedy', 'Have a competent site supervisor review.') }"
        )

    st.download_button(
        "Download safety report (JSON)",
        data=_report_bytes(report),
        file_name="construction_safety_report.json",
        mime="application/json",
        key="download_safety_report",
    )
    if report.get("limitations"):
        st.caption(report["limitations"])


def _render_crack_report(report):
    if report.get("analysis_mode") == "demo":
        st.warning("Demonstration output: the uploaded image was not visually analyzed.")
    else:
        st.warning("Image-based screening only. A licensed structural engineer must assess the structure before repair decisions.")

    cols = st.columns(3)
    cols[0].metric("Defect classification", report.get("defect_type", "Needs review"))
    width = report.get("estimated_width_mm")
    cols[1].metric("Estimated width", (str(width) + " mm") if width is not None else "Not estimated")
    cols[2].metric("Urgency", report.get("urgency", "Engineering review"))

    st.subheader("Likely contributing factors")
    for cause in report.get("root_causes", []):
        st.markdown("- " + str(cause))
    st.subheader("Recommended next steps")
    for repair in report.get("recommended_repairs", []):
        st.markdown("- " + str(repair))
    st.info(report.get("engineering_note", "Crack width and cause cannot be confirmed from a photograph alone."))
    st.download_button(
        "Download crack report (JSON)",
        data=_report_bytes(report),
        file_name="crack_diagnostics_report.json",
        mime="application/json",
        key="download_crack_report",
    )


def _safety_page(api_key, model):
    st.markdown("## Site Safety & PPE Audit")
    st.markdown("Upload a site photo for a structured visual screening of visible PPE and hazards.")
    uploaded = st.file_uploader("Construction site photo", type=["jpg", "jpeg", "png"], key="safety_image")
    if uploaded:
        left, right = st.columns([1, 1.3])
        with left:
            st.image(uploaded, caption="Uploaded site photo", use_container_width=True)
        with right:
            st.markdown("#### Audit scope")
            st.markdown("Helmets, high-visibility vests, safety footwear and harness visibility, plus observable site hazards.")
            st.caption("A photo cannot confirm PPE certification, footwear construction, harness anchorage, or conditions outside the frame.")
            if st.button("Run PPE audit", type="primary", use_container_width=True):
                with st.spinner("Reviewing the photo…"):
                    if not api_key:
                        report = demo_safety_report()
                        report["limitations"] = "No Gemini key was provided; these are placeholder demonstration results, not findings about the uploaded photo."
                    else:
                        try:
                            report = analyze_safety_image(uploaded.getvalue(), uploaded.type, api_key, model)
                        except Exception as exc:
                            st.error("Gemini analysis failed: " + str(exc))
                            report = demo_safety_report()
                            report["limitations"] = "Gemini was unavailable; these are placeholder demonstration results, not findings about the uploaded photo."
                    report["analyzed_at"] = datetime.now(timezone.utc).isoformat()
                    st.session_state["safety_report"] = report
    if st.session_state.get("safety_report"):
        _render_safety_report(st.session_state["safety_report"])
    st.caption("Reference framing: OSHA PPE concepts are used as a screening lens. IS 456 addresses plain and reinforced concrete design; it is not a PPE standard. Apply applicable local regulations and project safety plans.")


def _crack_page(api_key, model):
    st.markdown("## Crack Diagnostics & Structural Integrity")
    st.markdown("Upload a clear close-up of a concrete or masonry surface. Include a scale reference where possible.")
    uploaded = st.file_uploader("Concrete or wall photo", type=["jpg", "jpeg", "png"], key="crack_image")
    if uploaded:
        left, right = st.columns([1, 1.3])
        with left:
            st.image(uploaded, caption="Uploaded surface photo", use_container_width=True)
        with right:
            st.markdown("#### Screening categories")
            st.markdown("Hairline · Settlement · Structural shear · Thermal expansion · Spalling")
            st.caption("Width estimates from a photo are approximate and depend on image scale, perspective and focus.")
            if st.button("Assess surface condition", type="primary", use_container_width=True):
                with st.spinner("Preparing preliminary assessment…"):
                    if not api_key:
                        report = demo_crack_report()
                        report["engineering_note"] = "No Gemini key was provided; this is a placeholder, not a diagnosis of the uploaded image. Consult a structural engineer."
                    else:
                        try:
                            report = analyze_crack_image(uploaded.getvalue(), uploaded.type, api_key, model)
                        except Exception as exc:
                            st.error("Gemini analysis failed: " + str(exc))
                            report = demo_crack_report()
                            report["engineering_note"] = "Gemini was unavailable; this is a placeholder, not a diagnosis of the uploaded image. Consult a structural engineer."
                    report["analyzed_at"] = datetime.now(timezone.utc).isoformat()
                    st.session_state["crack_report"] = report
    if st.session_state.get("crack_report"):
        _render_crack_report(st.session_state["crack_report"])


def _planning_page(pollinations_key):
    st.markdown("## Planning & Real Estate Valuation")
    st.markdown("Build an indicative budget, material quantity and asset value snapshot from project assumptions.")
    with st.form("planning_inputs"):
        c1, c2 = st.columns(2)
        with c1:
            structure = st.selectbox("Structure type", ["Residential", "Commercial", "Industrial", "Institutional"])
            area = st.number_input("Built-up area (sq ft)", min_value=100, max_value=2_000_000, value=2_000, step=100)
        with c2:
            tier = st.selectbox("Location tier", ["Tier 1", "Tier 2", "Tier 3"], index=1)
            completion = st.slider("Construction completion", min_value=0, max_value=100, value=35, step=1, format="%d%%")
        submitted = st.form_submit_button("Update estimate", type="primary")
    if submitted or "project_estimate" not in st.session_state:
        st.session_state["project_estimate"] = estimate_project(structure, area, tier, completion)
        st.session_state["project_inputs"] = {"structure": structure, "area": area, "tier": tier, "completion": completion}

    estimate = st.session_state["project_estimate"]
    inputs = st.session_state["project_inputs"]
    st.progress(inputs["completion"] / 100, text=f"Milestone progress · {inputs['completion']}% complete")
    row1 = st.columns(3)
    row1[0].metric("Indicative project budget", format_inr(estimate["project_budget_inr"]))
    row1[1].metric("Capex incurred to date", format_inr(estimate["capex_incurred_inr"]))
    row1[2].metric("Current pro-rata asset value", format_inr(estimate["asset_value_inr"]))
    st.caption("Completed built-up property benchmark: " + format_inr(estimate["asset_value_on_completion_inr"]))
    row2 = st.columns(3)
    row2[0].metric("Estimated steel", f"{estimate['steel_kg']:,.0f} kg", f"{estimate['steel_tonnes']:,.1f} tonnes")
    row2[1].metric("Estimated cement", f"{estimate['cement_bags']:,.0f} bags")
    row2[2].metric("Budget remaining", format_inr(estimate["budget_remaining_inr"]))
    st.markdown('<div class="panel"><b>Assumptions</b><br>' + estimate["assumptions"] + '</div>', unsafe_allow_html=True)

    st.markdown("### Conceptual 3D rendering")
    prompt = rendering_prompt(inputs["structure"], inputs["area"], inputs["tier"])
    prompt_key = "render_prompt_" + str(round(inputs["area"])) + "_" + inputs["structure"] + "_" + inputs["tier"]
    prompt = st.text_area("Generated architectural prompt", prompt, height=100, key=prompt_key)
    if pollinations_key:
        if st.button("Generate concept image with Pollinations Flux", type="primary", key="generate_concept"):
            with st.spinner("Generating a conceptual image…"):
                try:
                    st.session_state["concept_image"] = _generate_pollinations_image(prompt, pollinations_key)
                    st.session_state["concept_prompt"] = prompt
                except (HTTPError, URLError, TimeoutError, ValueError) as exc:
                    st.error("Pollinations image generation failed: " + str(exc))
        if st.session_state.get("concept_image") and st.session_state.get("concept_prompt") == prompt:
            st.image(st.session_state["concept_image"], caption="AI-generated concept image", use_container_width=True)
    else:
        st.info("Add a Pollinations API key in the sidebar to generate the image here, or copy the prompt and paste it into Pollinations.")
        st.link_button("Open Pollinations", "https://pollinations.ai/", help="The generated prompt is shown above; paste it into the service.")
    st.caption("Concept art is illustrative and is not a construction drawing or approved design.")


def _weather_card(condition):
    content = {
        "High Wind": ("High", "Pause crane lifts, suspended loads and work at height when wind exceeds equipment or site limits. Secure loose materials, inspect scaffold ties and re-check before restart."),
        "Heavy Rain": ("High", "Stop exposed electrical work where water ingress is possible. Isolate affected circuits, protect excavations from runoff, check access routes and reassess slopes. Protect fresh concrete and follow the approved curing plan."),
        "Extreme Heat": ("High", "Schedule strenuous work for cooler hours, provide shade and drinking water, enforce rest and heat illness monitoring. Protect concrete from rapid moisture loss and follow the mix designer's curing procedure."),
        "Normal": ("Routine", "Continue the approved daily toolbox talk, inspect access and edge protection, verify PPE, and monitor local forecasts for changing conditions."),
    }
    level, advice = content[condition]
    st.markdown(f"### {condition} · {level} alert")
    st.warning(advice) if level == "High" else st.success(advice)
    st.caption("Weather alerts are general planning prompts. Follow site-specific stop-work limits, equipment manuals and local forecasts.")


def _assistant_page(api_key, model):
    st.markdown("## Daily Site Assistant & Weather Advisory")
    condition = st.selectbox("Today's site weather", ["Normal", "High Wind", "Heavy Rain", "Extreme Heat"], key="weather_condition")
    _weather_card(condition)
    st.markdown("### Construction engineering assistant")
    if not api_key:
        st.info("Demo assistant is active. Add a Gemini API key in the sidebar to enable model responses.")
    history = st.session_state.setdefault("chat_history", [])
    for message in history[-12:]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    question = st.chat_input("Ask about site planning, concrete, materials or safety…")
    if question:
        history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Preparing a response…"):
                try:
                    answer = answer_construction_question(question, history, condition, api_key, model)
                except Exception as exc:
                    answer = "The Gemini assistant is unavailable right now (" + str(exc) + "). For urgent or safety-critical decisions, contact the responsible site engineer and follow the approved method statement."
                st.markdown(answer)
        history.append({"role": "assistant", "content": answer})
        st.rerun()


with st.sidebar:
    st.markdown("# 🏗️ Site Intelligence")
    st.caption("Skill Wallet Capstone · Project 1")
    configured_key = _secret_key("GEMINI_API_KEY")
    api_key = st.text_input(
        "Google Gemini API key",
        type="password",
        value=configured_key,
        help="Used only for requests in this session. You can also configure GEMINI_API_KEY in Streamlit secrets.",
        key="gemini_api_key_input",
    )
    model = st.text_input("Gemini model", value=os.getenv("GEMINI_MODEL", DEFAULT_MODEL), help="Change this if your API project uses a different available model.")
    if api_key:
        st.success("Gemini mode enabled")
    else:
        st.info("Demo mode · no API key entered")
    pollinations_key = st.text_input(
        "Pollinations API key (optional)",
        type="password",
        value=_secret_key("POLLINATIONS_API_KEY"),
        help="Used only when you click Generate concept image. Image generation may consume your Pollinations balance.",
        key="pollinations_api_key_input",
    )
    st.markdown("---")
    st.markdown("### Architecture")
    st.markdown("`Streamlit UI` → `Gemini multimodal API` → `validated JSON`\n\nPlanning estimates and weather protocols run locally. No database is used.")
    st.markdown("### Feature navigation")
    feature = st.radio(
        "Open module",
        FEATURES,
        label_visibility="collapsed",
        key="feature_navigation",
        on_change=_select_tab_from_sidebar if _has_stateful_tabs else None,
    )
    st.markdown("---")
    st.caption("Screening and planning support only. Confirm safety and structural decisions with qualified professionals and applicable codes.")


st.markdown(
    '<div class="hero"><div class="eyebrow">Skill Wallet Capstone · Project 1</div>'
    '<h1>Multimodal Construction Intelligence Platform</h1>'
    '<p>Turn site observations into clearer safety, structural and project decisions.</p></div>',
    unsafe_allow_html=True,
)

if _has_stateful_tabs:
    safety_tab, crack_tab, planning_tab, assistant_tab = st.tabs(
        FEATURES,
        default=feature,
        key="active_module_tab",
        on_change=_select_sidebar_from_tab,
    )
    if safety_tab.open:
        with safety_tab:
            _safety_page(api_key, model.strip() or DEFAULT_MODEL)
    if crack_tab.open:
        with crack_tab:
            _crack_page(api_key, model.strip() or DEFAULT_MODEL)
    if planning_tab.open:
        with planning_tab:
            _planning_page(pollinations_key)
    if assistant_tab.open:
        with assistant_tab:
            _assistant_page(api_key, model.strip() or DEFAULT_MODEL)
elif feature == "Site Safety & PPE Audit":
    _safety_page(api_key, model.strip() or DEFAULT_MODEL)
elif feature == "Crack Diagnostics":
    _crack_page(api_key, model.strip() or DEFAULT_MODEL)
elif feature == "Planning & Valuation":
    _planning_page(pollinations_key)
else:
    _assistant_page(api_key, model.strip() or DEFAULT_MODEL)
