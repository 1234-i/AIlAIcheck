# Domain Model

## Core Domain Objects

## 1) File Record
Fields:
- `file_id` (UUID)
- `batch_id` (UUID)
- `file_name` (string)
- `storage_uri` (string)
- `checksum` (string)
- `page_count` (int)
- `doc_type` (string)
- `primary_group` (enum)
- `related_groups` (array[enum])
- `confidence` (float)
- `classification_evidence` (array[evidence-lite])
- `created_at`, `updated_at`

## 2) Person Record
Fields:
- `person_id` (UUID)
- `project_id` (UUID)
- `name` (string)
- `id_no_hash` (string)
- `role` (string)
- `certifications` (array)
- `medical_valid_until` (date)
- `insurance_status` (string)
- `source_file_ids` (array[UUID])

## 3) Equipment Record
Fields:
- `equipment_id` (UUID)
- `project_id` (UUID)
- `name` (string)
- `model` (string)
- `serial_no` (string)
- `inspection_status` (string)
- `last_inspection_date` (date)
- `operator_person_ids` (array[UUID])
- `source_file_ids` (array[UUID])

## 4) Project Record
Fields:
- `project_id` (UUID)
- `project_name` (string)
- `section_name` (string)
- `contractor_name` (string)
- `contract_no` (string)
- `start_date` (date)
- `planned_end_date` (date)
- `risk_level` (string)

## 5) Audit Issue
Fields:
- `issue_id` (UUID)
- `batch_id` (UUID)
- `rule_id` (string)
- `clause_id` (string)
- `audit_group` (enum)
- `audit_object` (string)
- `checkpoint` (string)
- `result` (enum: pass/fail/warn)
- `severity` (enum)
- `issue_description` (string)
- `rectification_suggestion` (string|null)
- `confidence` (float)
- `evidence_chain` (array[Evidence])
- `flags` (contradiction/template_suspected/etc.)

## 6) Rule Object
Fields:
- `rule_id` (string)
- `clause_id` (string)
- `rule_name` (string)
- `audit_group` (enum)
- `audit_object` (string)
- `checkpoint` (string)
- `evidence_required` (int)
- `logic_type` (enum)
- `severity` (enum)
- `issue_template` (string)
- `rectification_template` (string)
- `enabled` (bool)
- `version` (semver)

## 7) Evidence Object
Fields:
- `evidence_id` (UUID)
- `source_file_id` (UUID)
- `source_file_name` (string)
- `page` (int)
- `snippet` (string)
- `locator` (object|null)
- `field_path` (string)
- `extracted_field_source` (string: classification/extraction/normalization)
- `rule_id` (string)
- `clause_id` (string)

## 8) Doc Type to Audit Group Mapping
Audit groups:
1. `PROJECT_ADMISSION_LEGAL`
2. `PERSONNEL_CONSISTENCY_QUALIFICATION`
3. `HSE_RISK_DOCUMENTS`
4. `EQUIPMENT_TOOLS_MATERIALS`
5. `TRAINING_PERMIT_CLOSURE`
6. `CROSS_DOCUMENT_CONFLICT_SCAN`

Indicative mapping:
- Medical examination record -> primary `PERSONNEL_CONSISTENCY_QUALIFICATION`, related `CROSS_DOCUMENT_CONFLICT_SCAN`
- Insurance policy -> primary `PROJECT_ADMISSION_LEGAL`, related `PERSONNEL_CONSISTENCY_QUALIFICATION`
- Labor contract -> primary `PROJECT_ADMISSION_LEGAL`, related `PERSONNEL_CONSISTENCY_QUALIFICATION`
- Social insurance material -> primary `PERSONNEL_CONSISTENCY_QUALIFICATION`
- Personnel qualification review form -> primary `PERSONNEL_CONSISTENCY_QUALIFICATION`
- Key role personnel review form -> primary `PERSONNEL_CONSISTENCY_QUALIFICATION`, related `TRAINING_PERMIT_CLOSURE`
- Entry permit -> primary `TRAINING_PERMIT_CLOSURE`, related `PERSONNEL_CONSISTENCY_QUALIFICATION`
- Safety education/training record -> primary `TRAINING_PERMIT_CLOSURE`
- All-staff commitment letter -> primary `HSE_RISK_DOCUMENTS`
- JSA -> primary `HSE_RISK_DOCUMENTS`, related `CROSS_DOCUMENT_CONFLICT_SCAN`
- Construction organization plan -> primary `HSE_RISK_DOCUMENTS`, related `EQUIPMENT_TOOLS_MATERIALS`
- Emergency response plan -> primary `HSE_RISK_DOCUMENTS`, related `CROSS_DOCUMENT_CONFLICT_SCAN`
- Equipment/tool/material inspection form -> primary `EQUIPMENT_TOOLS_MATERIALS`, related `CROSS_DOCUMENT_CONFLICT_SCAN`
- Project commencement report -> primary `PROJECT_ADMISSION_LEGAL`
- HSE commitment letter -> primary `PROJECT_ADMISSION_LEGAL`, related `HSE_RISK_DOCUMENTS`
- Construction contract -> primary `PROJECT_ADMISSION_LEGAL`, related `CROSS_DOCUMENT_CONFLICT_SCAN`
