# Native Multimodal PDF Strategy

## Primary Strategy
Use Gemini native multimodal input to read PDFs directly via `inline_data(base64)`.

## Why OCR-First Is Not Primary
- OCR introduces additional error layers and layout loss.
- Native PDF understanding preserves semantic and structural signals.
- Lower pipeline complexity for MVP and better traceability to source pages.

## Fallback Policy
- OCR is an architecture hook only in MVP.
- Fallback may be introduced later for scanned-image-only PDFs or low-confidence extraction.

## Direct PDF Read Flow
1. Load PDF bytes from object storage.
2. Encode bytes as base64.
3. Build Gemini request payload using `inline_data`.
4. Send request to relay endpoint.
5. Parse model output as strict JSON.
6. Validate against schema and confidence thresholds.

## Document Type Recognition Flow
1. Filename classifier predicts `doc_type` and group with rule-based hints.
2. If confidence below threshold or ambiguous naming, call Gemini content classifier.
3. Merge filename and content signals using confidence policy.
4. Persist final classification with evidence snippets.

## Template-Based Extraction Flow
1. Determine target extraction schema by `doc_type`.
2. Prompt Gemini with schema contract and extraction instructions.
3. Receive structured JSON candidate.
4. Validate with Pydantic/JSON schema.
5. On validation failure, optionally retry with correction prompt.
6. Persist validated extraction and source evidence references.

## Confidence and Validation
- Each classification/extraction output includes confidence score.
- Hard validation: schema validity, required fields, enumerations.
- Soft validation: semantic consistency checks (date order, identity alignment).
- Low-confidence outputs are marked for review or second-pass processing.

## Gemini Relay Configuration
- `GEMINI_BASE_URL=https://reelxai.com/v1beta`
- `GEMINI_AUDIT_MODEL=gemini-3.1-pro-preview`
- `GEMINI_API_KEY` loaded from environment, never hardcoded.

## Adapter Isolation Principle
- Business services depend on provider-neutral interface.
- Gemini-specific transport, payload, and retries are isolated in adapter/client modules.
