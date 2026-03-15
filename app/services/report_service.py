from __future__ import annotations

from pathlib import Path

from sqlmodel import Session

from app.reports.exporter import export_report_excel
from app.reports.generator import generate_report


def build_report(session: Session, batch_id: str, export_dir: str = "./examples/outputs") -> dict:
    report = generate_report(session=session, batch_id=batch_id)
    report_dict = report.model_dump()

    xlsx_path = Path(export_dir) / f"report_{batch_id}.xlsx"
    excel_path = export_report_excel(report_dict, str(xlsx_path))

    report.export_links = {
        "json": f"/api/v1/batches/{batch_id}/report",
        "excel": excel_path,
    }
    session.add(report)
    session.commit()
    session.refresh(report)

    return report.model_dump()
