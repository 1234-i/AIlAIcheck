from __future__ import annotations

import json
from pathlib import Path


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_simple_pdf(path: Path, lines: list[str]) -> None:
    line_commands = []
    y = 760
    for line in lines:
        line_commands.append(f"BT /F1 11 Tf 40 {y} Td ({_escape_pdf_text(line)}) Tj ET")
        y -= 16
    stream = "\n".join(line_commands) + "\n"

    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Count 1 /Kids [3 0 R] >>\nendobj\n",
        (
            "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>\nendobj\n"
        ),
        f"4 0 obj\n<< /Length {len(stream.encode('utf-8'))} >>\nstream\n{stream}endstream\nendobj\n",
        "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]

    content = "%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(content.encode("utf-8")))
        content += obj

    xref_pos = len(content.encode("utf-8"))
    content += f"xref\n0 {len(objects) + 1}\n"
    content += "0000000000 65535 f \n"
    for offset in offsets[1:]:
        content += f"{offset:010d} 00000 n \n"

    content += (
        "trailer\n"
        f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        "startxref\n"
        f"{xref_pos}\n"
        "%%EOF\n"
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))


def build_dataset() -> None:
    root = Path("examples/golden_dataset/v1")
    pdf_dir = root / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    extraction_labels = []

    samples = [
        ("construction_contract", "contract_normal_01.pdf", {"project_name": "Alpha LNG Upgrade", "contractor_name": "ACME EPC Co.", "contract_no": "HT-2026-001", "effective_date": "2026-01-01"}),
        ("construction_contract", "contract_normal_02.pdf", {"project_name": "Alpha LNG Upgrade", "contractor_name": "ACME EPC Co.", "contract_no": "HT-2026-001", "effective_date": "2026-01-01"}),
        ("construction_contract", "contract_problem_03.pdf", {"project_name": "Alpha LNG Upgrade", "contractor_name": "ACME EPC Co.", "contract_no": "HT-2026-001", "effective_date": "2026-01-01"}),
        ("construction_contract", "contract_problem_04.pdf", {"project_name": "Alpha LNG Upgrade", "contractor_name": "ACME EPC Co.", "contract_no": "HT-2026-001", "effective_date": "2026-01-01"}),
        ("construction_contract", "contract_normal_05.pdf", {"project_name": "Alpha LNG Upgrade", "contractor_name": "ACME EPC Co.", "contract_no": "HT-2026-001", "effective_date": "2026-01-01"}),
        ("personnel_qualification_review_form", "qualification_zhang_normal_01.pdf", {"project_name": "Alpha LNG Upgrade", "person_name": "Zhang San", "id_no": "A-10001", "role": "scaffolder", "certificate_no": "CERT-ZS-001", "certificate_valid_until": "2025-12-31"}),
        ("personnel_qualification_review_form", "qualification_zhang_problem_02.pdf", {"project_name": "Alpha LNG Upgrade", "person_name": "Zhang San", "id_no": "A-10001", "role": "scaffolder", "certificate_no": "CERT-ZS-001", "certificate_valid_until": "2025-12-31"}),
        ("personnel_qualification_review_form", "qualification_li_normal_03.pdf", {"project_name": "Alpha LNG Upgrade", "person_name": "Li Si", "id_no": "A-20002", "role": "scaffolder", "certificate_no": "CERT-ZS-001", "certificate_valid_until": "2025-12-31"}),
        ("personnel_qualification_review_form", "qualification_li_problem_04.pdf", {"project_name": "Alpha LNG Upgrade", "person_name": "Li Si", "id_no": "A-20002", "role": "scaffolder", "certificate_no": "CERT-ZS-001", "certificate_valid_until": "2025-12-31"}),
        ("personnel_qualification_review_form", "qualification_wang_normal_05.pdf", {"project_name": "Alpha LNG Upgrade", "person_name": "Wang Wu", "id_no": "A-30003", "role": "scaffolder", "certificate_no": "CERT-ZS-001", "certificate_valid_until": "2025-12-31"}),
        ("entry_permit", "permit_zhang_normal_01.pdf", {"project_name": "Alpha LNG Upgrade", "person_name": "Zhang San", "id_no": "A-10001", "role": "scaffolder", "permit_no": "EP-2026-009", "permit_date": "2026-02-10"}),
        ("entry_permit", "permit_zhang_supervisor_problem_02.pdf", {"project_name": "Alpha LNG Upgrade", "person_name": "Zhang San", "id_no": "A-10001", "role": "supervisor", "permit_no": "EP-2026-009", "permit_date": "2026-02-10"}),
        ("entry_permit", "permit_li_normal_03.pdf", {"project_name": "Alpha LNG Upgrade", "person_name": "Li Si", "id_no": "A-20002", "role": "scaffolder", "permit_no": "EP-2026-009", "permit_date": "2026-02-10"}),
        ("entry_permit", "permit_li_supervisor_problem_04.pdf", {"project_name": "Alpha LNG Upgrade", "person_name": "Li Si", "id_no": "A-20002", "role": "supervisor", "permit_no": "EP-2026-009", "permit_date": "2026-02-10"}),
        ("entry_permit", "permit_wang_normal_05.pdf", {"project_name": "Alpha LNG Upgrade", "person_name": "Wang Wu", "id_no": "A-30003", "role": "scaffolder", "permit_no": "EP-2026-009", "permit_date": "2026-02-10"}),
        ("safety_education_training_record", "training_zhang_normal_01.pdf", {"project_name": "Alpha LNG Upgrade", "person_name": "Zhang San", "id_no": "A-10001", "training_topic": "Entry Safety Briefing", "training_date": "2026-02-05", "trainer": "Safety Officer Chen"}),
        ("safety_education_training_record", "training_zhang_problem_02.pdf", {"project_name": "Alpha LNG Upgrade", "person_name": "Zhang San", "id_no": "A-10001", "training_topic": "Entry Safety Briefing", "training_date": "2026-02-05", "trainer": "Safety Officer Chen"}),
        ("safety_education_training_record", "training_li_normal_03.pdf", {"project_name": "Alpha LNG Upgrade", "person_name": "Li Si", "id_no": "A-20002", "training_topic": "Entry Safety Briefing", "training_date": "2026-02-05", "trainer": "Safety Officer Chen"}),
        ("safety_education_training_record", "training_li_problem_04.pdf", {"project_name": "Alpha LNG Upgrade", "person_name": "Li Si", "id_no": "A-20002", "training_topic": "Entry Safety Briefing", "training_date": "2026-02-05", "trainer": "Safety Officer Chen"}),
        ("safety_education_training_record", "training_wang_normal_05.pdf", {"project_name": "Alpha LNG Upgrade", "person_name": "Wang Wu", "id_no": "A-30003", "training_topic": "Entry Safety Briefing", "training_date": "2026-02-05", "trainer": "Safety Officer Chen"}),
    ]

    for doc_type, file_name, data in samples:
        lines = [f"doc_type: {doc_type}"]
        lines.extend([f"{k}: {v}" for k, v in data.items()])
        if "problem" in file_name:
            lines.append("note: problematic sample")
        write_simple_pdf(pdf_dir / file_name, lines)

        extraction_labels.append(
            {
                "file_name": file_name,
                "doc_type": doc_type,
                "is_problematic": "problem" in file_name,
                "fields_to_eval": list(data.keys()),
                "gold_data": data,
            }
        )

    extraction_label_path = root / "extraction_gold_labels.jsonl"
    extraction_label_path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in extraction_labels),
        encoding="utf-8",
    )

    audit_labels = {
        "batches": [
            {
                "batch_name": "batch_clean_chain",
                "file_names": [
                    "contract_normal_01.pdf",
                    "qualification_zhang_normal_01.pdf",
                    "permit_zhang_normal_01.pdf",
                    "training_zhang_normal_01.pdf",
                ],
                "expected_hit_rules": ["R-V2-022"]
            },
            {
                "batch_name": "batch_role_mismatch",
                "file_names": [
                    "contract_normal_02.pdf",
                    "qualification_zhang_problem_02.pdf",
                    "permit_zhang_supervisor_problem_02.pdf",
                    "training_zhang_problem_02.pdf",
                ],
                "expected_hit_rules": ["R-V2-022", "R-V2-025"]
            },
            {
                "batch_name": "batch_missing_training",
                "file_names": [
                    "contract_problem_03.pdf",
                    "qualification_li_normal_03.pdf",
                    "permit_li_normal_03.pdf"
                ],
                "expected_hit_rules": ["R-V2-004", "R-V2-022", "R-V2-026", "R-V2-029"]
            },
            {
                "batch_name": "batch_chain_gaps_multi",
                "file_names": [
                    "contract_problem_04.pdf",
                    "permit_wang_normal_05.pdf",
                    "training_li_problem_04.pdf",
                ],
                "expected_hit_rules": ["R-V2-002", "R-V2-026", "R-V2-029"]
            }
        ]
    }
    (root / "audit_gold_labels.json").write_text(json.dumps(audit_labels, ensure_ascii=False, indent=2), encoding="utf-8")

    (root / "README.md").write_text(
        "# Golden Dataset v1\n\n"
        "- Total PDFs: 20\n"
        "- Doc types: construction_contract, personnel_qualification_review_form, entry_permit, safety_education_training_record\n"
        "- Includes normal and problematic samples\n"
        "- Labels: extraction_gold_labels.jsonl, audit_gold_labels.json\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    build_dataset()
