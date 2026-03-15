# API Specification (v1)

Base path: `/api/v1`

## Common Response Envelope
```json
{
  "request_id": "string",
  "data": {},
  "error": null
}
```

## 1) Upload API
### `POST /batches/uploads`
- Content type: `multipart/form-data`
- Fields:
  - `files[]`: PDF files
  - `uploader` (optional)
  - `project_hint` (optional)

Response example:
```json
{
  "request_id": "req_001",
  "data": {
    "batch_id": "b_123",
    "file_ids": ["f_1", "f_2"],
    "status": "UPLOADED"
  },
  "error": null
}
```

## 2) Batch Query API
### `GET /batches/{batch_id}`
Response fields:
- `batch_id`, `status`, `created_at`, `completed_at`, `summary_counts`

## 3) File Classification API
### `POST /batches/{batch_id}/classify`
- Triggers classification workflow (idempotent).

### `GET /files/{file_id}/classification`
Response fields:
- `doc_type`
- `primary_group`
- `related_groups`
- `confidence`
- `classification_evidence`

## 4) Extraction API
### `POST /batches/{batch_id}/extract`
- Triggers extraction workflow for classifiable files.

### `GET /files/{file_id}/extraction`
Response fields:
- `schema_name`
- `schema_version`
- `validated_json`
- `confidence`
- `validation_errors`

## 5) Audit Task API
### `POST /batches/{batch_id}/audit`
- Runs rule engine for target batch.

### `GET /batches/{batch_id}/issues`
- Query params: `severity`, `group`, `page`, `page_size`

Response issue item includes:
- `issue_id`, `rule_id`, `clause_id`, `audit_group`, `severity`, `issue_description`, `confidence`, `evidence_chain`

## 6) Report Export API
### `POST /batches/{batch_id}/report`
- Generates report artifacts.

### `GET /batches/{batch_id}/report`
- Returns canonical JSON report.

### `GET /batches/{batch_id}/report.xlsx`
- Returns Excel file download.

## 7) Human Review API
### `POST /review/issues/{issue_id}`
Request:
```json
{
  "action": "accept",
  "comment": "Evidence is sufficient",
  "updated_fields": {
    "severity": "HIGH"
  }
}
```

## 8) Rule Draft API
### `POST /rules/draft-from-policy`
- Uploads policy text/PDF for AI draft rule generation.

### `POST /rules/approve`
- Approves reviewed rule drafts into active library.

## Error Model
```json
{
  "request_id": "req_001",
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "file type not supported",
    "details": {}
  }
}
```

## Idempotency & Retry
- Trigger endpoints accept optional `Idempotency-Key` header.
- Duplicate trigger requests with same key return original task reference.
- Task failures expose retriable status and reason.
