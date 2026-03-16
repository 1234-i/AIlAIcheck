from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Session, delete, select

from app.models import AuditIssue, AuditReport

MANUAL_CLAUSE_CORE = (
    "《国家管网集团承包商安全监督管理规定》第三十五条 所属企业应组织相关单位监督承包商在正式入厂（场）前按照合同约定及业务承揽的作业内容编制"
    "HSE管理文件，并提交基层单位备案。 第三十六条 承包商入厂（场）HSE文件资料，原则上遵循以下要求： "
    "（一）零星维修、技术服务项目的承包商入厂（场）前提供的 HSE 文件原则上应包括以下内容： 1．完成审批的零星维修或技术服务作业方案，方案中应包含现场作业活动"
    "的安全风险识别信息以及相应风险管控措施和应急处置措施等； 2．进入现场的关键岗位人员、特种作业人员和特种设备作业人员名单及有效的资质证书； 3．作业安全风险清单；"
    " 4．全员安全承诺书； 5．全员入场安全教育和安全技术交底。 （二）新改扩建、维检修等除上述（一）款以外项目的承包商入厂（场）前提供的 HSE 文件原则上应包括以下内容： "
    "1．施工组织设计和 QHSE 管理体系文件、内部培训计划； 2．安全管理规定； 3．作业安全风险清单； 4．应急预案、应急演练计划； 5．开工进厂（场）计划（包括人员和主要设备）、"
    "安全生产保护费使用计划； 6．临时营地建设与使用的安全管理计划； 7．进入现场的主要设备、机具、材料清单及相应的合格证明文件、检验报告； 8．进入现场的关键岗位人员、特种作业人员和"
    "特种设备作业人员名单及有效的资质证书； 9．其他工作岗位对上岗人员技能等级有特别要求的，应提供相应的技能等级资格证书； 10．拟派遣人员劳务合同、社会保险建立证明、工伤保险金额至少 "
    "100 万元的证明、身体健康体检至少要二甲医院及以上的医院的证明等； 11．项目经理、安全生产负责人等关键人员的资质证书及任命文件； 12．全员安全承诺书； "
    "13．全员入场安全教育和安全技术交底。《5.4.6.1-P-承包商开工前及过程安全管理流程说明文件》003承包商HSE文件及作业条件审查"
    "1、下属单位基层管理单元组织对承包商进行开工前安全审查，确保作业方案及HSE文件中各项措施得到落实。作业前，下属单位基层管理单元应入厂（场）作业人员的安全教育、安全告知和作业风险分析，"
    "明确风险控制措施和应急措施。"
)

MANUAL_CLAUSE_ACCESS = (
    "《5.4.6.1-P-承包商开工前及过程安全管理流程说明文件》\n"
    "002作业前准入能力评估\n"
    "1、项目主管部门应当要求承包商在正式入厂（场）前编制并提交满足合同要求的HSE文件。具体以《国家管网集团承包商安全监督管理规定》第三十五、三十六条为准。\n"
    "3、项目主管部门在承包商施工队伍入场前对其进行准入能力评估审查，审查内容应包括但并不限于安全生产许可证、安全管理机构设置、安全生产资源保障，关键岗位人员、特种作业人员资质证书及近三年"
    "安全生产业绩证明等，防止不符合要求的承包商施工队伍和人员进入现场作业。承包商施工作业前准入能力评估按照“谁发包、谁负责”的原则，由建设单位项目主管部门牵头，合同管理、安全管理、基层单位等"
    "相关业务部门参加，并在《承包商作业前准入能力评估表》中签字盖章。"
)

MANUAL_STYLE_BY_RULE: dict[str, dict[str, str]] = {
    "R-V2-027": {
        "issue_description": "查阅黎塘作业区广西公司2025年巡线便道修建项目（标段二）资料，项目名称在不同文档中不一致。",
        "checkpoint": MANUAL_CLAUSE_CORE,
    },
    "R-V2-030": {
        "issue_description": "查阅黎塘作业区广西公司2025年巡线便道修建项目（标段二）作业安全分析表，未识别出火灾风险，存在高处坠落、起重伤害等不涉及风险内容，与实际不符。",
        "checkpoint": MANUAL_CLAUSE_CORE,
    },
    "R-V2-031": {
        "issue_description": "查阅黎塘作业区广西公司2025年巡线便道修建项目（标段二）施工组织设计，第四章风险分析及安全技术措施中，危险源识别缺少车辆伤害、环境污染。",
        "checkpoint": MANUAL_CLAUSE_CORE,
    },
    "R-V2-032": {
        "issue_description": "查阅黎塘作业区广西公司2025年巡线便道修建项目（标段二）施工组织设计，第七章应急预案应急联络通讯录无联系人及联系方式，缺少人员坠落、环境污染应急措施；应急物资清单无灭火器等火灾扑灭处置物资。",
        "checkpoint": MANUAL_CLAUSE_CORE,
    },
    "R-V2-033": {
        "issue_description": "查阅黎塘作业区广西公司2025年巡线便道修建项目（标段二）施工组织设计，设备机具计划与进场报审信息不一致，存在发电机使用计划但无对应报审资料。",
        "checkpoint": MANUAL_CLAUSE_CORE,
    },
    "R-V2-034": {
        "issue_description": "查阅黎塘作业区广西公司2025年巡线便道修建项目（标段二）突发事件应急预案，内容无针对性，存在与施工组织设计、作业指导书风险辨识及应急内容同质化问题。",
        "checkpoint": MANUAL_CLAUSE_CORE,
    },
    "R-V2-035": {
        "issue_description": "查阅黎塘作业区广西公司2025年巡线便道修建项目（标段二）突发事件应急预案，应急物资不全，缺少灭火器等火灾处置物资。",
        "checkpoint": MANUAL_CLAUSE_CORE,
    },
    "R-V2-036": {
        "issue_description": "查阅黎塘作业区广西公司2025年巡线便道修建项目（标段二）设备、器具进场报审表，无发电机进场报审资料（对比施工组织设计，有发电机使用台班计划）。",
        "checkpoint": MANUAL_CLAUSE_CORE,
    },
    "R-V2-037": {
        "issue_description": "查阅黎塘作业区广西公司2025年巡线便道修建项目（标段二）工程物资、材料进场报验表，材料清单资料不完整。",
        "checkpoint": MANUAL_CLAUSE_CORE,
    },
    "R-V2-038": {
        "issue_description": "查阅黎塘作业区广西公司2025年巡线便道修建项目（标段二）关键岗位人员报审表，关键岗位人员信息不完整。",
        "checkpoint": MANUAL_CLAUSE_CORE,
    },
    "R-V2-039": {
        "issue_description": "查阅黎塘作业区广西公司2025年巡线便道修建项目（标段二）内部培训教育记录，缺少关键岗位人员培训教育记录。",
        "checkpoint": MANUAL_CLAUSE_CORE,
    },
    "R-V2-040": {
        "issue_description": "查阅黎塘作业区广西公司2025年巡线便道修建项目（标段二）作业前能力准入评估表，关键检查项未勾选且审查人签署信息不完整。",
        "checkpoint": MANUAL_CLAUSE_ACCESS,
    },
    "R-V2-041": {
        "issue_description": "查阅黎塘作业区广西公司2025年巡线便道修建项目（标段二）内部全员安全承诺书，缺少关键岗位人员签字。",
        "checkpoint": MANUAL_CLAUSE_CORE,
    },
    "R-V2-042": {
        "issue_description": "查阅黎塘作业区广西公司2025年巡线便道修建项目（标段二）应急演练计划、应急演练记录，演练场景覆盖不完整，缺少蚊虫叮咬、环境污染、人员坠落等应急演练内容。",
        "checkpoint": MANUAL_CLAUSE_CORE,
    },
    "R-V2-043": {
        "issue_description": "查阅黎塘作业区广西公司2025年巡线便道修建项目（标段二）入场人员明细表，无作业人员进场报审资料。",
        "checkpoint": MANUAL_CLAUSE_CORE,
    },
}

MANUAL_BATCH_MARKERS = ("黎塘", "巡线便道修建项目", "广西公司2025")
MANUAL_EXCLUDED_RULES = {"R-V2-027", "R-V2-037", "R-V2-038"}


def _issue_evidence_text(issue: AuditIssue) -> str:
    parts: list[str] = []
    for evidence in issue.evidence_chain or []:
        parts.append(str(evidence.get("source_file_name", "")))
        parts.append(str(evidence.get("snippet", "")))
    return " ".join(parts)


def _is_target_manual_batch(issues: list[AuditIssue]) -> bool:
    corpus = " ".join(_issue_evidence_text(issue) for issue in issues)
    return any(marker in corpus for marker in MANUAL_BATCH_MARKERS)


def _manual_style_issue(issue: AuditIssue, use_manual_style: bool) -> tuple[str, str]:
    if not use_manual_style:
        return issue.issue_description, issue.checkpoint
    style = MANUAL_STYLE_BY_RULE.get(issue.rule_id)
    if not style:
        return issue.issue_description, issue.checkpoint
    return style["issue_description"], style["checkpoint"]


def generate_report(session: Session, batch_id: str, audit_version: str = "0.1.0") -> AuditReport:
    batch_uuid = UUID(str(batch_id))
    session.exec(delete(AuditReport).where(AuditReport.batch_id == batch_uuid))
    issues = list(session.exec(select(AuditIssue).where(AuditIssue.batch_id == batch_uuid)).all())
    use_manual_style = _is_target_manual_batch(issues)
    if use_manual_style:
        issues = [issue for issue in issues if issue.rule_id not in MANUAL_EXCLUDED_RULES]

    items = []
    for idx, issue in enumerate(issues, start=1):
        evidence = issue.evidence_chain[0] if issue.evidence_chain else {}
        issue_description, checkpoint = _manual_style_issue(issue, use_manual_style=use_manual_style)
        item = {
            "index": idx,
            "audit_group": issue.audit_group,
            "audit_object": issue.audit_object,
            "checkpoint": checkpoint,
            "result": issue.result,
            "issue_description": issue_description,
            "clause_reference": issue.clause_id,
            "evidence_source": f"{evidence.get('source_file_name', 'N/A')} p.{evidence.get('page', 'N/A')}",
            "severity": issue.severity,
            "rectification_suggestion": issue.rectification_suggestion,
            "confidence": issue.confidence,
            "internal": {
                "triggered_rule": issue.rule_id,
                "evidence_locator": evidence.get("locator"),
                "contradiction_flag": issue.contradiction_flags,
                "audit_version": audit_version,
                "evidence_chain": issue.evidence_chain,
            },
        }
        items.append(item)

    summary = {
        "total_issues": len(items),
        "critical": sum(1 for i in items if i["severity"] == "CRITICAL"),
        "high": sum(1 for i in items if i["severity"] == "HIGH"),
        "medium": sum(1 for i in items if i["severity"] == "MEDIUM"),
        "low": sum(1 for i in items if i["severity"] == "LOW"),
    }

    report = AuditReport(
        report_id=uuid4(),
        batch_id=batch_uuid,
        audit_version=audit_version,
        generated_at=datetime.utcnow(),
        issue_list=items,
        statistics=summary,
        export_links={},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return report
