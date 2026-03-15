from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlmodel import Session, delete, select

from app.models import EquipmentMaster, ExtractionRecord, FileRecord, PersonMaster, ProjectProfile

ROLE_SYNONYMS = {
    "scaffolder": "scaffolder",
    "scaffold worker": "scaffolder",
    "脚手架工": "scaffolder",
    "supervisor": "supervisor",
    "site supervisor": "supervisor",
    "监护": "supervisor",
}


def _hash_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_name(name: str | None) -> str:
    if not name:
        return ""
    return re.sub(r"\s+", "", name).strip().lower()


def _normalize_id(id_no: str | None) -> str:
    if not id_no:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", id_no).upper()


def _normalize_role(role: str | None) -> str:
    if not role:
        return ""
    key = role.strip().lower()
    return ROLE_SYNONYMS.get(key, key)


def _source_from_doc_type(doc_type: str) -> str:
    if doc_type == "personnel_qualification_review_form":
        return "qualification"
    if doc_type == "entry_permit":
        return "permit"
    if doc_type in {"safety_education_training_record", "training_record"}:
        return "training"
    return "other"


def _build_person_key(person_name: str | None, id_no: str | None, role: str | None) -> str:
    normalized_id = _normalize_id(id_no)
    if normalized_id:
        return f"id:{normalized_id}"
    return f"name_role:{_normalize_name(person_name)}:{_normalize_role(role)}"


def normalize_batch_facts(session: Session, batch_id: str) -> dict[str, Any]:
    batch_uuid = UUID(str(batch_id))
    files = list(session.exec(select(FileRecord).where(FileRecord.batch_id == batch_uuid)).all())
    file_map = {file.file_id: file for file in files}
    file_ids = list(file_map.keys())

    session.exec(delete(PersonMaster).where(PersonMaster.batch_id == batch_uuid))
    session.exec(delete(ProjectProfile).where(ProjectProfile.batch_id == batch_uuid))
    session.exec(delete(EquipmentMaster).where(EquipmentMaster.batch_id == batch_uuid))

    if not file_ids:
        session.commit()
        return {
            "batch_id": batch_id,
            "doc_types": [],
            "doc_type_index": {},
            "project_names": [],
            "contractor_names": [],
            "persons": [],
            "person_chain_gaps": [],
            "evidence": [],
        }

    records = list(session.exec(select(ExtractionRecord).where(ExtractionRecord.file_id.in_(file_ids))).all())

    project_names: set[str] = set()
    contractor_names: set[str] = set()
    doc_type_index: dict[str, list[dict[str, Any]]] = {}
    evidence_items: list[dict[str, Any]] = []
    person_accumulator: dict[str, dict[str, Any]] = {}

    for record in records:
        file_record = file_map.get(record.file_id)
        if not file_record:
            continue

        payload = record.validated_json or record.raw_model_json
        doc_type = file_record.doc_type or "unknown"
        doc_type_index.setdefault(doc_type, []).append(
            {
                "file_id": str(file_record.file_id),
                "file_name": file_record.file_name,
                "doc_type": doc_type,
                "data": payload,
            }
        )

        project_name = payload.get("project_name")
        contractor_name = payload.get("contractor_name")
        if project_name:
            project_names.add(str(project_name).strip())
        if contractor_name:
            contractor_names.add(str(contractor_name).strip())

        evidence_items.append(
            {
                "source_file_id": str(file_record.file_id),
                "source_file_name": file_record.file_name,
                "page": 1,
                "snippet": f"Normalized data from {file_record.file_name}",
                "field_path": "validated_json",
                "extracted_field_source": "extraction",
                "locator": None,
            }
        )

        source_tag = _source_from_doc_type(doc_type)
        person_name = payload.get("person_name") or payload.get("employee_name")
        person_id = payload.get("id_no")
        role = payload.get("role")
        if person_name:
            key = _build_person_key(person_name=person_name, id_no=person_id, role=role)
            state = person_accumulator.setdefault(
                key,
                {
                    "canonical_name": person_name,
                    "normalized_name": _normalize_name(person_name),
                    "normalized_id": _normalize_id(person_id),
                    "id_no_hash": _hash_id(_normalize_id(person_id) or _normalize_name(person_name)),
                    "roles": set(),
                    "roles_by_source": {},
                    "source_file_ids": set(),
                    "source_file_names": set(),
                    "chain_flags": {"qualification": False, "permit": False, "training": False},
                    "certs": [],
                },
            )
            normalized_role = _normalize_role(role)
            if normalized_role:
                state["roles"].add(normalized_role)
                state["roles_by_source"][source_tag] = normalized_role
            state["source_file_ids"].add(str(file_record.file_id))
            state["source_file_names"].add(file_record.file_name)
            if source_tag in state["chain_flags"]:
                state["chain_flags"][source_tag] = True
            if payload.get("certificate_no"):
                state["certs"].append(
                    {
                        "certificate_no": payload.get("certificate_no"),
                        "certificate_valid_until": payload.get("certificate_valid_until"),
                        "source": source_tag,
                    }
                )

    project = ProjectProfile(
        batch_id=batch_uuid,
        project_name=sorted(project_names)[0] if project_names else None,
        contractor_name=sorted(contractor_names)[0] if contractor_names else None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(project)

    normalized_people: list[dict[str, Any]] = []
    person_chain_gaps: list[dict[str, Any]] = []

    for state in person_accumulator.values():
        roles = sorted(state["roles"])
        role_value = roles[0] if roles else None
        chain_flags = state["chain_flags"]
        missing_links = [name for name, flag in chain_flags.items() if not flag]

        person_model = PersonMaster(
            batch_id=batch_uuid,
            name=state["canonical_name"],
            id_no_hash=state["id_no_hash"],
            role=role_value,
            certs=state["certs"],
            insurance_status=None,
            employment_links=sorted(state["source_file_ids"]),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(person_model)

        person_record = {
            "person_key": state["normalized_id"] or state["normalized_name"],
            "person_name": state["canonical_name"],
            "roles": roles,
            "roles_by_source": state["roles_by_source"],
            "source_file_ids": sorted(state["source_file_ids"]),
            "source_file_names": sorted(state["source_file_names"]),
            "chain_flags": chain_flags,
            "missing_chain_links": missing_links,
        }
        normalized_people.append(person_record)

        if missing_links:
            person_chain_gaps.append(
                {
                    "person_name": state["canonical_name"],
                    "missing_links": missing_links,
                    "source_file_ids": sorted(state["source_file_ids"]),
                    "source_file_names": sorted(state["source_file_names"]),
                }
            )

    session.commit()

    return {
        "batch_id": batch_id,
        "doc_types": sorted({file.doc_type for file in files if file.doc_type}),
        "doc_type_index": doc_type_index,
        "project_names": sorted(project_names),
        "contractor_names": sorted(contractor_names),
        "persons": normalized_people,
        "person_chain_gaps": person_chain_gaps,
        "evidence": evidence_items,
    }
