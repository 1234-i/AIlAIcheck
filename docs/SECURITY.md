# Security Guidelines

## API Key Management
- `GEMINI_API_KEY` must come from environment variables only.
- Never hardcode keys in code, docs, examples, tests, or scripts.
- Rotate API keys periodically and on exposure suspicion.

## Environment Variable Policy
- Use `.env.example` placeholders only.
- Load secrets through runtime environment or secret manager.
- Validate required env vars at startup without logging secret values.

## Redaction Strategy
- Redact tokens, keys, and authorization headers from logs and traces.
- Avoid storing raw identity numbers; store hash/tokenized identifiers where possible.

## Logging Safety
- Structured logs only; no full PDF payload logs.
- Error logs should include request IDs and redacted context.
- Debug logging of model payloads disabled by default.

## File Storage Safety
- Store uploaded files in S3-compatible object storage with least-privilege credentials.
- Use server-side encryption and signed URLs for controlled access.
- Enforce content-type and extension checks for uploads.

## Data Retention and Access
- Configure retention policy by environment and compliance requirements.
- Restrict batch/file/report access by role and project scope.
- Keep immutable audit trail for issue review actions.

## No Hardcoded Secrets
- Hardcoded secrets are forbidden.
- CI checks should fail if secret patterns are detected.
