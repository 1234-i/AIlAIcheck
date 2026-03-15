# JSON Schema Contracts

This file defines canonical schema shapes used across API, persistence boundaries, and worker messages.

## 1) File Metadata Schema
```json
{
  "type": "object",
  "required": ["file_id", "batch_id", "file_name", "storage_uri", "doc_type", "primary_group", "confidence"],
  "properties": {
    "file_id": {"type": "string"},
    "batch_id": {"type": "string"},
    "file_name": {"type": "string"},
    "storage_uri": {"type": "string"},
    "doc_type": {"type": "string"},
    "primary_group": {"type": "string"},
    "related_groups": {"type": "array", "items": {"type": "string"}},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "classification_evidence": {"type": "array", "items": {"$ref": "#/definitions/evidenceLite"}}
  },
  "definitions": {
    "evidenceLite": {
      "type": "object",
      "required": ["page", "snippet"],
      "properties": {
        "page": {"type": "integer", "minimum": 1},
        "snippet": {"type": "string"}
      }
    }
  }
}
```

## 2) Extraction Result Schema
```json
{
  "type": "object",
  "required": ["file_id", "schema_name", "schema_version", "validated_json", "confidence"],
  "properties": {
    "file_id": {"type": "string"},
    "schema_name": {"type": "string"},
    "schema_version": {"type": "string"},
    "validated_json": {"type": "object"},
    "raw_model_json": {"type": "object"},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "validation_errors": {"type": "array", "items": {"type": "string"}}
  }
}
```

## 3) Rule Schema
```json
{
  "type": "object",
  "required": [
    "rule_id", "clause_id", "rule_name", "audit_group", "audit_object", "checkpoint",
    "evidence_required", "logic_type", "severity", "issue_template", "rectification_template", "enabled", "version"
  ],
  "properties": {
    "rule_id": {"type": "string"},
    "clause_id": {"type": "string"},
    "rule_name": {"type": "string"},
    "audit_group": {"type": "string"},
    "audit_object": {"type": "string"},
    "checkpoint": {"type": "string"},
    "evidence_required": {"type": "integer", "minimum": 1},
    "logic_type": {"type": "string"},
    "severity": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
    "issue_template": {"type": "string"},
    "rectification_template": {"type": "string"},
    "enabled": {"type": "boolean"},
    "version": {"type": "string"}
  }
}
```

## 4) Audit Issue Schema
```json
{
  "type": "object",
  "required": ["issue_id", "batch_id", "rule_id", "clause_id", "audit_group", "checkpoint", "severity", "issue_description", "evidence_chain", "confidence"],
  "properties": {
    "issue_id": {"type": "string"},
    "batch_id": {"type": "string"},
    "rule_id": {"type": "string"},
    "clause_id": {"type": "string"},
    "audit_group": {"type": "string"},
    "audit_object": {"type": "string"},
    "checkpoint": {"type": "string"},
    "result": {"type": "string", "enum": ["PASS", "FAIL", "WARN"]},
    "severity": {"type": "string"},
    "issue_description": {"type": "string"},
    "rectification_suggestion": {"type": ["string", "null"]},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "evidence_chain": {"type": "array", "minItems": 1, "items": {"$ref": "#/definitions/evidence"}},
    "flags": {"type": "object"}
  },
  "definitions": {
    "evidence": {
      "type": "object",
      "required": ["evidence_id", "source_file_id", "source_file_name", "page", "snippet", "field_path", "extracted_field_source", "rule_id", "clause_id"],
      "properties": {
        "evidence_id": {"type": "string"},
        "source_file_id": {"type": "string"},
        "source_file_name": {"type": "string"},
        "page": {"type": "integer", "minimum": 1},
        "snippet": {"type": "string"},
        "field_path": {"type": "string"},
        "extracted_field_source": {"type": "string"},
        "locator": {"type": ["object", "null"]},
        "rule_id": {"type": "string"},
        "clause_id": {"type": "string"}
      }
    }
  }
}
```

## 5) Report Schema
```json
{
  "type": "object",
  "required": ["report_id", "batch_id", "audit_version", "generated_at", "summary", "items"],
  "properties": {
    "report_id": {"type": "string"},
    "batch_id": {"type": "string"},
    "audit_version": {"type": "string"},
    "generated_at": {"type": "string", "format": "date-time"},
    "summary": {"type": "object"},
    "items": {"type": "array", "items": {"$ref": "#/definitions/reportItem"}}
  },
  "definitions": {
    "reportItem": {
      "type": "object",
      "required": ["index", "audit_group", "audit_object", "checkpoint", "result", "issue_description", "clause_reference", "evidence_source", "severity", "confidence"],
      "properties": {
        "index": {"type": "integer"},
        "audit_group": {"type": "string"},
        "audit_object": {"type": "string"},
        "checkpoint": {"type": "string"},
        "result": {"type": "string"},
        "issue_description": {"type": "string"},
        "clause_reference": {"type": "string"},
        "evidence_source": {"type": "string"},
        "severity": {"type": "string"},
        "rectification_suggestion": {"type": ["string", "null"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1}
      }
    }
  }
}
```

## 6) Evidence Schema
```json
{
  "type": "object",
  "required": ["evidence_id", "source_file_id", "source_file_name", "page", "snippet", "field_path", "extracted_field_source", "rule_id", "clause_id"],
  "properties": {
    "evidence_id": {"type": "string"},
    "source_file_id": {"type": "string"},
    "source_file_name": {"type": "string"},
    "page": {"type": "integer", "minimum": 1},
    "snippet": {"type": "string"},
    "field_path": {"type": "string"},
    "extracted_field_source": {"type": "string"},
    "locator": {"type": ["object", "null"]},
    "rule_id": {"type": "string"},
    "clause_id": {"type": "string"}
  }
}
```
