# Multimodal Construction Intelligence Platform

Skill Wallet Capstone Project 1: a zero-database Streamlit application for construction-site screening and project planning.

## Features

- **Site Safety & PPE Audit:** analyzes JPG/PNG site photos for visible helmets, high-visibility vests, safety footwear and harnesses, plus visible hazards and remedies. Exports a JSON report.
- **Crack Diagnostics:** screens concrete or masonry images for likely defect category, a scale-dependent width estimate, likely causes, repair options and urgency. Exports a JSON report.
- **Planning & Valuation:** calculates indicative INR budget, capex, pro-rata built-up asset value, steel and cement quantities, and completion progress from transparent local benchmarks.
- **Daily Assistant & Weather Advisory:** displays weather-specific general protocols and offers a multi-turn site assistant.
- **Concept visualization:** creates a Pollinations prompt and can generate a Flux image with an optional Pollinations API key; without a key, copy the prompt into the service.
- **Demo mode:** the planner and weather cards work without an API key. Safety/crack placeholder reports are explicitly marked as demonstrations and do not claim to analyze uploaded photos.

## Run locally

Python 3.9 or newer is supported. From this directory:

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Enter a Google Gemini API key in the sidebar to enable image analysis and model chat. The key is held by Streamlit for the session and is not written to a database or file. For a private deployment, configure `GEMINI_API_KEY` as an environment variable or Streamlit secret; optionally configure `POLLINATIONS_API_KEY` for in-app image generation. You may also set `GEMINI_MODEL`; the default is `gemini-3.8-flash`.

For Streamlit Community Cloud, deploy this repository and set `GEMINI_API_KEY` in **App settings → Secrets**. The key is optional; without it the app runs in demo mode.

Example `.streamlit/secrets.toml` for local development (do not commit secrets):

```toml
GEMINI_API_KEY = "your-key"
POLLINATIONS_API_KEY = "your-key"
```

## Data handling

No database is used. Uploaded images are processed in the active Streamlit session and sent to Google only when the user selects a live Gemini analysis action. Do not upload sensitive site imagery unless your organization permits the configured model provider to process it. Pollinations receives a prompt only when the user generates an image or visits the service.

## Planning assumptions

The estimator uses fixed illustrative INR/sq ft benchmarks by structure type and location tier. Capex is assumed to track physical completion. Steel and cement totals are rough gross allowances, not a bill of quantities. Market value uses a completed built-up property benchmark, prorated by completion, and excludes land. Replace these defaults with a local quantity surveyor's estimate, project drawings, a BOQ and current comparable sales before making investment or procurement decisions.

Pollinations image generation is optional and requires a Pollinations API key; generation runs only after clicking the button and may consume account balance. The prompt remains available to copy when no key is configured.

## Tests

Run the local estimate, prompt and demo-contract checks with:

```bash
python -m unittest discover -s tests -v
```

## Safety and engineering scope

AI outputs are preliminary screening aids. An image cannot establish PPE certification, boot toe construction, harness fit or anchorage, crack depth/activity, structural capacity, hidden hazards, or legal compliance. OSHA references are framed as general PPE concepts; IS 456 is a concrete design code, not a PPE regulation. Follow applicable local requirements and obtain qualified onsite review for safety-critical or structural decisions.
