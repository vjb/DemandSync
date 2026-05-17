# Technical Debt and Architectural Mocks

This document serves as an explicit ledger of all hardcoded values, fail-open fallbacks, and mocked integrations currently existing in the DemandSync codebase. This document must be resolved before any production deployment.

## 1. Google Cloud Agent Builder Fallback (RESOLVED)
**Location:** `demandsync_v2_agent.py` -> `query_agent_builder_policy()`
**Status:** Fixed. The system now strictly halts execution via `raise RuntimeError` if Agent Builder is unreachable or empty, ensuring compliance is strictly enforced.

## 2. Gemini API Key Simulation Fallbacks (RESOLVED)
**Location:** `demandsync_v2_agent.py` -> `get_embedding()`, `calculate_dynamic_price()`, `generate_ad_creative()`
**Status:** Fixed. Configuration validation is enforced on boot. If `GEMINI_API_KEY` is not present, initialization halts with `ValueError`. All generative fallback returns have been purged.

## 3. Vertex AI Imagen Quota & Timeout Fallbacks (RESOLVED)
**Location:** `demandsync_v2_agent.py` -> `generate_ad_creative()`
**Status:** Fixed. An asynchronous retry loop (max 3 retries, exponential backoff) now catches `429 RESOURCE_EXHAUSTED` errors. If retries fail, it strictly returns `"ERROR"` which the frontend parses to explicitly display a `GENERATION FAILED` UI state instead of masking it with stock images.

## 4. Geospatial Coordinate Hardcoding
**Location:** `static/index.html` -> `triggerEvent()`
**Issue:** The UI uses a hardcoded conditional map to translate dropdown selections (e.g., "Central Park", "Midtown") into Lat/Lon coordinates (`[40.7812, -73.9665]`). 
**TODO:** Integrate a live geocoding API (e.g., Google Maps Geocoding API) to dynamically resolve event text to bounding boxes and feed those exact coordinates into the MongoDB Atlas `$geoNear` query.

## 5. Sales Simulation and Supply Chain Actuation (RESOLVED)
**Location:** `demandsync_v2_agent.py` -> `execute_viral_sales()`, `generate_supplier_purchase_order()`, `main.py` -> `supplier_webhook()`
**Status:** Fixed. The local `print()` statement logic has been fully removed. The supply chain actuator now executes a live, asynchronous `urllib.request` HTTP POST to a structured REST API webhook (`/api/webhook/supplier`) to execute external ledger synchronization.
