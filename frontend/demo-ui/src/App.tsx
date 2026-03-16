import { useEffect, useMemo, useState } from 'react'
import {
  fetchIssues,
  fetchReport,
  getExcelDownloadUrl,
  triggerPipelineStep,
  uploadBatch,
} from './api'
import './App.css'
import type {
  AuditIssue,
  AuditReport,
  PipelineStepKey,
  StepRuntime,
  StepStatus,
} from './types'

const PIPELINE_STEPS: Array<{
  key: PipelineStepKey
  label: string
  description: string
}> = [
  {
    key: 'classify',
    label: '自动分类',
    description: '识别文档类型并归类审查分组。',
  },
  {
    key: 'extract',
    label: '结构化抽取',
    description: '抽取关键字段并完成结构校验。',
  },
  {
    key: 'audit',
    label: '规则审查',
    description: '执行规则引擎并生成问题项。',
  },
  {
    key: 'report',
    label: '生成报告',
    description: '汇总结果并输出可导出的审查报告。',
  },
]

const AUDIT_GROUP_LABEL_MAP: Record<string, string> = {
  PROJECT_ADMISSION_LEGAL: '项目准入与合规',
  PERSONNEL_CONSISTENCY_QUALIFICATION: '人员资质一致性',
  HSE_RISK_DOCUMENTS: '风险与作业资料',
  EQUIPMENT_TOOLS_MATERIALS: '设备工器具与材料',
  TRAINING_PERMIT_CLOSURE: '培训与准入闭环',
  CROSS_DOCUMENT_CONFLICT_SCAN: '跨文档冲突检查',
}

const SEVERITY_LABEL_MAP: Record<string, string> = {
  CRITICAL: '重大',
  HIGH: '高',
  MEDIUM: '中',
  LOW: '低',
}

const CHECKPOINT_TRANSLATION_MAP: Record<string, string> = {
  'Construction contract exists': '施工合同已提供',
  'Qualification form exists': '人员资质表已提供',
  'Entry permit exists': '入场许可已提供',
  'Training record exists': '培训记录已提供',
  'JSA exists': 'JSA风险分析已提供',
  'Contract no. not empty': '合同编号不能为空',
  'Project name not empty': '项目名称不能为空',
  'Person name not empty': '人员姓名不能为空',
  'ID number not empty': '身份证号不能为空',
  'Role not empty': '岗位信息不能为空',
  'Certificate number not empty': '证书编号不能为空',
  'Certificate valid-until not empty': '证书有效期不能为空',
  'Permit number not empty': '许可编号不能为空',
  'Permit date not empty': '许可日期不能为空',
  'Training date not empty': '培训日期不能为空',
  'Trainer not empty': '培训讲师不能为空',
  'Certificate date valid': '证书有效期需在有效范围内',
  'Training date should not be after permit date': '培训日期不得晚于许可日期',
  'Contract effective date should not be later than permit date': '合同生效日期不得晚于许可日期',
  'Qualification role equals permit role': '资质岗位与许可岗位需一致',
  'Permit holder must have training record': '许可持有人需具备培训记录',
  'Project name is consistent': '项目名称需跨文档一致',
  'Contractor name is consistent': '承包商名称需跨文档一致',
  'Qualification->Permit->Training chain complete': '资质-许可-培训链条需完整',
  'Each hazard has adequate controls': '每项作业风险均需配置对应控制措施',
}

const EN_TEXT_TRANSLATION_MAP: Record<string, string> = {
  'Qualification certificate is expired.': '资质证书已过期。',
  'Provide valid certificate.': '请提供有效证书。',
  'Provide valid qualification certificate.': '请提供有效的资质证书。',
  'Construction contract is missing.': '缺少施工合同文件。',
  'Upload construction contract.': '请补充上传施工合同。',
  'Personnel qualification form is missing.': '缺少人员资质审查表。',
  'Upload qualification form.': '请补充上传人员资质审查表。',
  'Entry permit is missing.': '缺少入场许可证文件。',
  'Upload entry permit.': '请补充上传入场许可证。',
  'Training record is missing.': '缺少安全培训记录。',
  'Upload training record.': '请补充上传安全培训记录。',
  'JSA document is missing.': '缺少JSA风险分析文件。',
  'Upload JSA document.': '请补充上传JSA风险分析文件。',
  'Contract number is missing.': '合同编号缺失。',
  'Fill contract number.': '请补充合同编号。',
  'Contract project name is missing.': '合同中的项目名称缺失。',
  'Fill project name in contract.': '请在合同中补充项目名称。',
  'Qualification person name is missing.': '资质表中的人员姓名缺失。',
  'Fill person name in qualification form.': '请在资质表中补充人员姓名。',
  'Qualification ID is missing.': '资质表中的身份证号缺失。',
  'Fill ID number in qualification form.': '请在资质表中补充身份证号。',
  'Qualification role is missing.': '资质表中的岗位信息缺失。',
  'Fill role in qualification form.': '请在资质表中补充岗位信息。',
  'Qualification certificate number is missing.': '资质证书编号缺失。',
  'Fill certificate number.': '请补充资质证书编号。',
  'Qualification certificate validity date is missing.': '资质证书有效期缺失。',
  'Fill certificate validity date.': '请补充资质证书有效期。',
  'Permit person name is missing.': '入场许可中的人员姓名缺失。',
  'Fill person name in permit.': '请在入场许可中补充人员姓名。',
  'Permit ID number is missing.': '入场许可中的身份证号缺失。',
  'Fill ID number in permit.': '请在入场许可中补充身份证号。',
  'Permit role is missing.': '入场许可中的岗位信息缺失。',
  'Fill role in permit.': '请在入场许可中补充岗位信息。',
  'Permit number is missing.': '入场许可编号缺失。',
  'Fill permit number.': '请补充入场许可编号。',
  'Permit date is missing.': '入场许可日期缺失。',
  'Fill permit date.': '请补充入场许可日期。',
  'Training person name is missing.': '培训记录中的人员姓名缺失。',
  'Fill person name in training record.': '请在培训记录中补充人员姓名。',
  'Training ID number is missing.': '培训记录中的身份证号缺失。',
  'Fill ID number in training record.': '请在培训记录中补充身份证号。',
  'Training date is missing.': '培训日期缺失。',
  'Fill training date.': '请补充培训日期。',
  'Trainer name is missing.': '培训讲师姓名缺失。',
  'Fill trainer name.': '请补充培训讲师姓名。',
  'Training date is later than permit date.': '培训日期晚于许可日期。',
  'Ensure training completed before permit issuance.': '请确保培训完成时间早于许可签发时间。',
  'Person role mismatch between qualification and permit.': '资质文件与入场许可中的岗位信息不一致。',
  'Unify role across documents.': '请统一各文档中的岗位信息。',
  'Permit holder has no training record.': '许可持有人未匹配到培训记录。',
  'Add matching training record.': '请补充对应的培训记录。',
  'Project name inconsistency detected.': '检测到项目名称跨文档不一致。',
  'Align project name across files.': '请统一各文件中的项目名称。',
  'Contractor name inconsistency detected.': '检测到承包商名称跨文档不一致。',
  'Align contractor name across files.': '请统一各文件中的承包商名称。',
  'Personnel chain has missing links.': '人员资质-许可-培训链条存在缺失。',
  'Close missing chain links.': '请补齐人员链条缺失资料。',
}

const FIELD_LABEL_MAP: Record<string, string> = {
  contract_no: '合同编号',
  project_name: '项目名称',
  person_name: '人员姓名',
  id_no: '身份证号',
  role: '岗位信息',
  certificate_no: '证书编号',
  certificate_valid_until: '证书有效期',
  permit_no: '许可编号',
  permit_date: '许可日期',
  training_date: '培训日期',
  trainer_name: '培训讲师',
  risk_items: '风险识别项',
  emergency_materials: '应急物资',
  equipment_plan: '设备机具计划',
  hazards_identified: '风险识别',
  equipment: '设备清单',
  materials: '材料清单',
  personnel: '关键岗位人员信息',
  attendees_signatures: '参训人员签名',
  items: '检查项',
  signatures: '签署信息',
  attendees: '参与人员',
}

function createInitialSteps(): Record<PipelineStepKey, StepRuntime> {
  return {
    classify: { status: 'idle' },
    extract: { status: 'idle' },
    audit: { status: 'idle' },
    report: { status: 'idle' },
  }
}

function normalizeText(value: unknown): string {
  return String(value ?? '').replace(/\s+/g, ' ').trim()
}

function fieldLabel(fieldKey: string): string {
  return FIELD_LABEL_MAP[fieldKey] ?? fieldKey
}

function translateEnglishText(raw: string | null | undefined): string {
  const normalized = normalizeText(raw)
  if (!normalized) {
    return '-'
  }

  if (EN_TEXT_TRANSLATION_MAP[normalized]) {
    return EN_TEXT_TRANSLATION_MAP[normalized]
  }

  if (CHECKPOINT_TRANSLATION_MAP[normalized]) {
    return CHECKPOINT_TRANSLATION_MAP[normalized]
  }

  const matchers: Array<{ pattern: RegExp; replace: (matches: RegExpMatchArray) => string }> = [
    {
      pattern: /^Date field '([^']+)' expired in (.+)$/,
      replace: (m) => `字段“${fieldLabel(m[1])}”在文件“${m[2]}”中已过期。`,
    },
    {
      pattern: /^Missing field '([^']+)' in (.+)$/,
      replace: (m) => `文件“${m[2]}”缺少字段“${fieldLabel(m[1])}”。`,
    },
    {
      pattern: /^Person '([^']+)' has inconsistent roles: qualification=([^ ]+) vs permit=(.+)$/,
      replace: (m) => `人员“${m[1]}”在资质与许可中的岗位不一致（资质：${m[2]}，许可：${m[3]}）。`,
    },
  ]

  for (const matcher of matchers) {
    const result = normalized.match(matcher.pattern)
    if (result) {
      return matcher.replace(result)
    }
  }

  return normalized
}

function translateCheckpoint(checkpoint: string | null | undefined): string {
  const normalized = normalizeText(checkpoint)
  if (!normalized) {
    return '未提供'
  }
  if (CHECKPOINT_TRANSLATION_MAP[normalized]) {
    return CHECKPOINT_TRANSLATION_MAP[normalized]
  }
  return translateEnglishText(normalized)
}

function formatDuration(durationMs?: number): string {
  if (!durationMs) {
    return '--'
  }
  return `${(durationMs / 1000).toFixed(2)}秒`
}

function formatDateTime(value?: string): string {
  if (!value) {
    return '-'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString('zh-CN', { hour12: false })
}

function getStatusLabel(status: StepStatus): string {
  if (status === 'running') return '执行中'
  if (status === 'done') return '已完成'
  if (status === 'failed') return '失败'
  return '待执行'
}

function getSeverityClass(severity: string): string {
  const upper = severity.toUpperCase()
  if (upper === 'CRITICAL') return 'sev-critical'
  if (upper === 'HIGH') return 'sev-high'
  if (upper === 'MEDIUM') return 'sev-medium'
  return 'sev-low'
}

function getSeverityLabel(severity: string): string {
  return SEVERITY_LABEL_MAP[severity.toUpperCase()] ?? severity
}

function getAuditGroupLabel(auditGroup: string): string {
  return AUDIT_GROUP_LABEL_MAP[auditGroup] ?? auditGroup
}

function getIssueFileName(issue: AuditIssue): string {
  return issue.evidence_chain?.[0]?.source_file_name ?? '未提供'
}

function getReportConclusion(report: AuditReport | null): string {
  if (!report) {
    return '等待报告生成后自动显示结论。'
  }

  const { critical, high, medium, low, total_issues: totalIssues } = report.statistics
  if (totalIssues === 0) {
    return '本批次未发现显著风险，可进入归档或抽检复核。'
  }
  if (critical > 0) {
    return '存在重大风险项，建议立即组织专项处置并完成复审闭环。'
  }
  if (high > 0) {
    return '存在高风险问题，建议优先整改并重新发起审查。'
  }
  if (medium > 0) {
    return '当前以中风险问题为主，建议制定分级整改计划。'
  }
  if (low > 0) {
    return '当前以低风险提示项为主，建议补齐资料后再校验。'
  }
  return '报告已生成，请结合业务场景进行复核。'
}

function App() {
  const [projectName, setProjectName] = useState('')
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [uploadedFileNames, setUploadedFileNames] = useState<string[]>([])
  const [fileIds, setFileIds] = useState<string[]>([])

  const [batchId, setBatchId] = useState('')
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'uploading' | 'done' | 'failed'>('idle')
  const [uploadError, setUploadError] = useState<string | null>(null)

  const [steps, setSteps] = useState<Record<PipelineStepKey, StepRuntime>>(createInitialSteps)
  const [runningStepKey, setRunningStepKey] = useState<PipelineStepKey | null>(null)
  const [isRunningAll, setIsRunningAll] = useState(false)

  const [issues, setIssues] = useState<AuditIssue[]>([])
  const [issuesTotal, setIssuesTotal] = useState(0)
  const [issuesLoading, setIssuesLoading] = useState(false)
  const [issuesError, setIssuesError] = useState<string | null>(null)

  const [severityFilter, setSeverityFilter] = useState('ALL')
  const [groupFilter, setGroupFilter] = useState('ALL')
  const [selectedIssue, setSelectedIssue] = useState<AuditIssue | null>(null)

  const [report, setReport] = useState<AuditReport | null>(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [reportError, setReportError] = useState<string | null>(null)

  const doneCount = useMemo(
    () => PIPELINE_STEPS.filter((step) => steps[step.key].status === 'done').length,
    [steps],
  )

  const failedStepIndex = useMemo(
    () => PIPELINE_STEPS.findIndex((step) => steps[step.key].status === 'failed'),
    [steps],
  )

  const runningStepIndex = useMemo(
    () => PIPELINE_STEPS.findIndex((step) => steps[step.key].status === 'running'),
    [steps],
  )

  const nextPendingStepIndex = useMemo(
    () => PIPELINE_STEPS.findIndex((step) => steps[step.key].status === 'idle'),
    [steps],
  )

  const allStepsDone = doneCount === PIPELINE_STEPS.length

  const currentStepIndex = useMemo(() => {
    if (!batchId) return -1
    if (runningStepIndex >= 0) return runningStepIndex
    if (failedStepIndex >= 0) return failedStepIndex
    if (nextPendingStepIndex >= 0) return nextPendingStepIndex
    return -1
  }, [batchId, failedStepIndex, nextPendingStepIndex, runningStepIndex])

  const allowedStepIndex = useMemo(() => {
    if (!batchId || runningStepKey || isRunningAll) return -1
    if (failedStepIndex >= 0) return failedStepIndex
    if (nextPendingStepIndex >= 0) return nextPendingStepIndex
    return -1
  }, [batchId, failedStepIndex, isRunningAll, nextPendingStepIndex, runningStepKey])

  const guideMessage = useMemo(() => {
    if (!batchId) {
      return '请先上传资料并创建批次，系统将自动进入第1步审查。'
    }
    if (runningStepIndex >= 0) {
      return `正在执行第${runningStepIndex + 1}步：${PIPELINE_STEPS[runningStepIndex].label}。`
    }
    if (failedStepIndex >= 0) {
      return `第${failedStepIndex + 1}步执行失败，请先重试当前步骤。`
    }
    if (nextPendingStepIndex >= 0) {
      return `下一步：第${nextPendingStepIndex + 1}步 ${PIPELINE_STEPS[nextPendingStepIndex].label}。`
    }
    return '审查流程已完成，请查看问题清单并导出报告。'
  }, [batchId, failedStepIndex, nextPendingStepIndex, runningStepIndex])

  const progressPercent = useMemo(() => {
    return (doneCount / PIPELINE_STEPS.length) * 100
  }, [doneCount])

  const severityOptions = useMemo(() => {
    const values = new Set<string>()
    for (const issue of issues) {
      values.add(issue.severity)
    }
    return Array.from(values).sort()
  }, [issues])

  const groupOptions = useMemo(() => {
    const values = new Set<string>()
    for (const issue of issues) {
      values.add(issue.audit_group)
    }
    return Array.from(values).sort()
  }, [issues])

  const filteredIssues = useMemo(() => {
    return issues.filter((issue) => {
      const severityMatch = severityFilter === 'ALL' || issue.severity === severityFilter
      const groupMatch = groupFilter === 'ALL' || issue.audit_group === groupFilter
      return severityMatch && groupMatch
    })
  }, [groupFilter, issues, severityFilter])

  useEffect(() => {
    if (filteredIssues.length === 0) {
      setSelectedIssue(null)
      return
    }

    const exists = selectedIssue
      ? filteredIssues.some((issue) => issue.issue_id === selectedIssue.issue_id)
      : false

    if (!exists) {
      setSelectedIssue(filteredIssues[0])
    }
  }, [filteredIssues, selectedIssue])

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files ? Array.from(event.target.files) : []
    setSelectedFiles(files)
  }

  const handleUpload = async () => {
    if (selectedFiles.length === 0) {
      setUploadError('请至少选择一个PDF文件。')
      return
    }

    setUploadStatus('uploading')
    setUploadError(null)

    const formData = new FormData()
    if (projectName.trim()) {
      formData.append('uploader', projectName.trim())
    }

    for (const file of selectedFiles) {
      formData.append('files', file)
    }

    try {
      const response = await uploadBatch(formData)
      const nextBatchId = typeof response.batch_id === 'string' ? response.batch_id : ''
      const nextFileIds = Array.isArray(response.file_ids)
        ? response.file_ids.map((item) => String(item))
        : []
      if (!nextBatchId) {
        throw new Error('上传成功但未返回批次编号，请重试。')
      }

      setBatchId(nextBatchId)
      setFileIds(nextFileIds)
      setUploadedFileNames(selectedFiles.map((file) => file.name))
      setUploadStatus('done')

      setSteps(createInitialSteps())
      setRunningStepKey(null)
      setIsRunningAll(false)

      setIssues([])
      setIssuesTotal(0)
      setIssuesError(null)
      setReport(null)
      setReportError(null)
      setSelectedIssue(null)
    } catch (error) {
      setUploadStatus('failed')
      setUploadError(error instanceof Error ? error.message : '上传失败，请重试。')
    }
  }

  const loadIssues = async (targetBatchId = batchId) => {
    if (!targetBatchId) {
      return
    }

    setIssuesLoading(true)
    setIssuesError(null)
    try {
      const response = await fetchIssues(targetBatchId, 1, 50)
      const items = Array.isArray(response.items) ? response.items : []
      setIssues(items)
      setIssuesTotal(typeof response.total === 'number' ? response.total : items.length)
    } catch (error) {
      setIssuesError(error instanceof Error ? error.message : '获取问题清单失败。')
    } finally {
      setIssuesLoading(false)
    }
  }

  const loadReport = async (targetBatchId = batchId) => {
    if (!targetBatchId) {
      return
    }

    setReportLoading(true)
    setReportError(null)
    try {
      const response = await fetchReport(targetBatchId)
      if (!response || typeof response !== 'object') {
        throw new Error('报告数据格式异常，请重试。')
      }
      setReport(response)
    } catch (error) {
      setReportError(error instanceof Error ? error.message : '获取审查报告失败。')
    } finally {
      setReportLoading(false)
    }
  }

  const runStepInternal = async (stepKey: PipelineStepKey): Promise<boolean> => {
    if (!batchId) {
      setUploadError('请先上传资料，生成批次后再执行审查流程。')
      return false
    }

    const startedAt = performance.now()
    setRunningStepKey(stepKey)

    setSteps((prev) => ({
      ...prev,
      [stepKey]: {
        status: 'running',
      },
    }))

    try {
      await triggerPipelineStep(batchId, stepKey)
      const durationMs = performance.now() - startedAt

      setSteps((prev) => ({
        ...prev,
        [stepKey]: {
          status: 'done',
          durationMs,
        },
      }))

      if (stepKey === 'audit') {
        await loadIssues(batchId)
      }
      if (stepKey === 'report') {
        await Promise.all([loadIssues(batchId), loadReport(batchId)])
      }
      return true
    } catch (error) {
      const durationMs = performance.now() - startedAt
      const message = error instanceof Error ? error.message : '步骤执行失败'

      setSteps((prev) => ({
        ...prev,
        [stepKey]: {
          status: 'failed',
          durationMs,
          error: message,
        },
      }))
      return false
    } finally {
      setRunningStepKey(null)
    }
  }

  const canRunSingleStep = (stepIndex: number): boolean => {
    return stepIndex === allowedStepIndex
  }

  const handleRunSingleStep = async (stepKey: PipelineStepKey, stepIndex: number) => {
    if (!canRunSingleStep(stepIndex)) {
      return
    }
    await runStepInternal(stepKey)
  }

  const handleRunAll = async () => {
    if (!batchId || runningStepKey || isRunningAll) {
      return
    }

    setIsRunningAll(true)

    let startIndex = 0
    if (failedStepIndex >= 0) {
      startIndex = failedStepIndex
    } else if (nextPendingStepIndex >= 0) {
      startIndex = nextPendingStepIndex
    } else {
      setSteps(createInitialSteps())
      startIndex = 0
    }

    for (let index = startIndex; index < PIPELINE_STEPS.length; index += 1) {
      const step = PIPELINE_STEPS[index]
      const success = await runStepInternal(step.key)
      if (!success) {
        break
      }
    }

    setIsRunningAll(false)
  }

  return (
    <div className="page-shell">
      <header className="top-hero">
        <div>
          <p className="eyebrow">工程审查工作台</p>
          <h1>HSE资料AI审查系统</h1>
          <p className="subtitle">用于项目资料自动分类、规则审查、问题追溯与报告导出的一体化工作页面。</p>
        </div>
        <div className="hero-stats">
          <div className="stat-card">
            <span>当前批次</span>
            <strong>{batchId || '尚未创建'}</strong>
          </div>
          <div className="stat-card">
            <span>资料数量</span>
            <strong>{uploadedFileNames.length}</strong>
          </div>
          <div className="stat-card">
            <span>已完成步骤</span>
            <strong>
              {doneCount}/{PIPELINE_STEPS.length}
            </strong>
          </div>
          <div className="stat-card">
            <span>问题总数</span>
            <strong>{issuesTotal}</strong>
          </div>
        </div>
      </header>

      <section className="order-banner">
        <span>审查顺序</span>
        <p>上传资料 -&gt; 自动分类 -&gt; 结构化抽取 -&gt; 规则审查 -&gt; 生成报告 -&gt; 查看问题 -&gt; 导出报告</p>
      </section>

      <section className="wizard-strip card">
        <div className="wizard-head">
          <h2>流程向导</h2>
          <p>{guideMessage}</p>
        </div>
        <div className="wizard-track" role="list" aria-label="流程向导">
          {PIPELINE_STEPS.map((step, index) => {
            const runtime = steps[step.key]
            const isCurrent = currentStepIndex === index
            const isDone = runtime.status === 'done'
            const isFailed = runtime.status === 'failed'
            const isRunning = runtime.status === 'running'
            const isPending = runtime.status === 'idle'

            return (
              <div
                key={step.key}
                role="listitem"
                className={`wizard-node ${
                  isFailed
                    ? 'wizard-failed'
                    : isRunning || isCurrent
                      ? 'wizard-current'
                      : isDone
                        ? 'wizard-done'
                        : isPending
                          ? 'wizard-pending'
                          : ''
                }`}
              >
                <span className="wizard-index">{index + 1}</span>
                <div>
                  <strong>{step.label}</strong>
                  <small>{getStatusLabel(runtime.status)}</small>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      <main className="content-grid">
        <section className="card upload-card">
          <div className="card-header">
            <h2>1. 资料上传</h2>
            <p>上传待审查PDF并创建批次。</p>
          </div>

          <div className="form-row">
            <label htmlFor="project-name">项目名称（可选）</label>
            <input
              id="project-name"
              type="text"
              value={projectName}
              onChange={(event) => setProjectName(event.target.value)}
              placeholder="例如：华东化工三期检修项目"
            />
          </div>

          <div className="form-row">
            <label htmlFor="pdf-files">选择PDF文件（可多选）</label>
            <input id="pdf-files" type="file" accept="application/pdf" multiple onChange={handleFileChange} />
          </div>

          <div className="upload-actions">
            <button
              className="btn primary"
              type="button"
              disabled={uploadStatus === 'uploading'}
              onClick={handleUpload}
            >
              {uploadStatus === 'uploading' ? '上传中...' : '上传并创建批次'}
            </button>

            <button
              className="btn accent"
              type="button"
              disabled={!batchId || !!runningStepKey || isRunningAll}
              onClick={handleRunAll}
            >
              {isRunningAll ? '流程执行中...' : allStepsDone ? '重新执行完整流程' : '执行完整流程'}
            </button>
          </div>

          {uploadError && <p className="error-text">{uploadError}</p>}

          <div className="upload-meta">
            <p>
              上传状态：
              <span className={`status-tag status-${uploadStatus}`}>
                {uploadStatus === 'idle' && '未上传'}
                {uploadStatus === 'uploading' && '上传中'}
                {uploadStatus === 'done' && '上传成功'}
                {uploadStatus === 'failed' && '上传失败'}
              </span>
            </p>
            <p>文件数量：{uploadedFileNames.length}</p>
          </div>

          <details className="batch-details">
            <summary>查看批次信息</summary>
            <p>
              <strong>批次编号：</strong>
              <span className="mono">{batchId || '-'}</span>
            </p>
            <details className="batch-tech-details">
              <summary>更多技术信息</summary>
              <p className="mono list-break">{fileIds.join(', ') || '-'}</p>
            </details>
          </details>

          <div className="file-list">
            <h3>已上传文件</h3>
            {uploadedFileNames.length === 0 ? (
              <p className="empty-text">尚未上传文件。</p>
            ) : (
              <ul>
                {uploadedFileNames.map((fileName, index) => (
                  <li key={`${fileName}-${index}`}>
                    <span>{fileName}</span>
                    <small className="mono">{fileIds[index] ?? '待分配编号'}</small>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <section className="card pipeline-card">
          <div className="card-header">
            <h2>2. 审查流程</h2>
            <p>严格顺序执行：完成当前步骤后，自动解锁下一步。</p>
          </div>

          <div className="progress-wrap">
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${progressPercent}%` }} />
            </div>
            <p>
              已完成 {doneCount} / {PIPELINE_STEPS.length} 步
            </p>
          </div>

          <div className="step-list">
            {PIPELINE_STEPS.map((step, index) => {
              const runtime = steps[step.key]
              const current = index === currentStepIndex && !allStepsDone
              const canRun = canRunSingleStep(index)

              return (
                <article
                  key={step.key}
                  className={`step-card ${current ? 'step-current' : ''} status-${runtime.status}`}
                >
                  <div className="step-head">
                    <span className="step-index">第{index + 1}步</span>
                    <span className={`status-tag status-${runtime.status}`}>{getStatusLabel(runtime.status)}</span>
                  </div>
                  <h3>{step.label}</h3>
                  <p>{step.description}</p>

                  {current && <p className="step-tip">当前步骤，请先完成本步再继续。</p>}
                  {!current && runtime.status === 'idle' && (
                    <p className="step-tip mute">等待前序步骤完成后自动解锁。</p>
                  )}
                  {runtime.error && <p className="error-text">{runtime.error}</p>}

                  <div className="step-foot">
                    <small>耗时：{formatDuration(runtime.durationMs)}</small>
                    <button
                      className="btn ghost"
                      type="button"
                      disabled={!canRun}
                      onClick={() => handleRunSingleStep(step.key, index)}
                    >
                      {runtime.status === 'failed' ? '重试当前步骤' : '执行当前步骤'}
                    </button>
                  </div>
                </article>
              )
            })}
          </div>
        </section>

        <section className="card issues-card">
          <div className="card-header row">
            <div>
              <h2>3. 问题清单</h2>
              <p>按风险等级和审查分组筛选问题，并查看证据链详情。</p>
            </div>
            <button className="btn ghost" type="button" disabled={!batchId || issuesLoading} onClick={() => loadIssues()}>
              {issuesLoading ? '刷新中...' : '刷新问题清单'}
            </button>
          </div>

          {uploadedFileNames.length > 0 && uploadedFileNames.length < 3 && (
            <p className="scope-hint">
              当前仅上传了 {uploadedFileNames.length} 份资料，系统只能输出当前覆盖范围内的问题，结果可能少于人工全量检查。
            </p>
          )}

          <div className="filters">
            <label>
              风险等级
              <select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}>
                <option value="ALL">全部</option>
                {severityOptions.map((item) => (
                  <option key={item} value={item}>
                    {getSeverityLabel(item)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              审查分组
              <select value={groupFilter} onChange={(event) => setGroupFilter(event.target.value)}>
                <option value="ALL">全部</option>
                {groupOptions.map((item) => (
                  <option key={item} value={item}>
                    {getAuditGroupLabel(item)}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {issuesError && <p className="error-text">{issuesError}</p>}

          {issuesLoading ? (
            <p className="empty-text">问题清单加载中...</p>
          ) : filteredIssues.length === 0 ? (
            <p className="empty-text">暂无问题数据。请先完成规则审查与报告生成，或调整筛选条件。</p>
          ) : (
            <div className="issues-layout">
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>检查问题</th>
                      <th>风险等级</th>
                      <th>审查分组</th>
                      <th>相关文件</th>
                      <th>制程条款内容</th>
                      <th>规则/条款</th>
                      <th>整改建议</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredIssues.map((issue) => (
                      <tr
                        key={issue.issue_id}
                        className={selectedIssue?.issue_id === issue.issue_id ? 'row-selected' : ''}
                        onClick={() => setSelectedIssue(issue)}
                      >
                        <td>{translateEnglishText(issue.issue_description)}</td>
                        <td>
                          <span className={`severity-badge ${getSeverityClass(issue.severity)}`}>
                            {getSeverityLabel(issue.severity)}
                          </span>
                        </td>
                        <td>{getAuditGroupLabel(issue.audit_group)}</td>
                        <td>{getIssueFileName(issue)}</td>
                        <td>{translateCheckpoint(issue.checkpoint)}</td>
                        <td>
                          {issue.rule_id} / {issue.clause_id}
                        </td>
                        <td>{translateEnglishText(issue.rectification_suggestion ?? '')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <aside className="issue-detail">
                <h3>问题详情</h3>
                {!selectedIssue ? (
                  <p className="empty-text">点击左侧问题行查看详情。</p>
                ) : (
                  <>
                    <p>
                      <strong>检查问题：</strong>
                      {translateEnglishText(selectedIssue.issue_description)}
                    </p>
                    <p>
                      <strong>风险等级：</strong>
                      <span className={`severity-badge ${getSeverityClass(selectedIssue.severity)}`}>
                        {getSeverityLabel(selectedIssue.severity)}
                      </span>
                    </p>
                    <p>
                      <strong>审查分组：</strong>
                      {getAuditGroupLabel(selectedIssue.audit_group)}
                    </p>
                    <p>
                      <strong>制程条款内容：</strong>
                      {translateCheckpoint(selectedIssue.checkpoint)}
                    </p>
                    <p>
                      <strong>规则编号：</strong>
                      {selectedIssue.rule_id}
                    </p>
                    <p>
                      <strong>条款编号：</strong>
                      {selectedIssue.clause_id}
                    </p>
                    <p>
                      <strong>整改建议：</strong>
                      {translateEnglishText(selectedIssue.rectification_suggestion ?? '暂无')}
                    </p>
                    <p>
                      <strong>置信度：</strong>
                      {Math.round((selectedIssue.confidence ?? 0) * 100)}%
                    </p>

                    <div className="evidence-block">
                      <strong>证据链</strong>
                      {selectedIssue.evidence_chain?.length ? (
                        <ul>
                          {selectedIssue.evidence_chain.map((evidence, idx) => (
                            <li
                              key={
                                evidence.evidence_id ??
                                `${evidence.source_file_id || 'unknown'}-${evidence.page || 0}-${idx}`
                              }
                            >
                              <p>
                                {evidence.source_file_name} / 第{evidence.page}页
                              </p>
                              <small>{translateEnglishText(evidence.snippet)}</small>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="empty-text">无证据链数据。</p>
                      )}
                    </div>
                  </>
                )}
              </aside>
            </div>
          )}
        </section>

        <section className="card report-card">
          <div className="card-header row">
            <div>
              <h2>4. 审查报告</h2>
              <p>查看报告摘要与风险分布，并导出Excel报告。</p>
            </div>
            <div className="report-actions">
              <button
                className="btn ghost"
                type="button"
                disabled={!batchId || reportLoading}
                onClick={() => loadReport()}
              >
                {reportLoading ? '刷新中...' : '刷新报告'}
              </button>
              <a
                className={`btn primary ${!batchId ? 'btn-disabled' : ''}`}
                href={batchId ? getExcelDownloadUrl(batchId) : '#'}
                onClick={(event) => {
                  if (!batchId) {
                    event.preventDefault()
                    setReportError('请先完成上传并生成报告。')
                  }
                }}
              >
                导出Excel报告
              </a>
            </div>
          </div>

          {reportError && <p className="error-text">{reportError}</p>}

          <div className="report-summary">
            <div className="summary-box">
              <span>总问题数</span>
              <strong>{report?.statistics.total_issues ?? 0}</strong>
            </div>
            <div className="summary-box">
              <span>高风险（含重大）</span>
              <strong>{(report?.statistics.critical ?? 0) + (report?.statistics.high ?? 0)}</strong>
            </div>
            <div className="summary-box">
              <span>中低风险</span>
              <strong>{(report?.statistics.medium ?? 0) + (report?.statistics.low ?? 0)}</strong>
            </div>
            <div className="summary-box">
              <span>报告时间</span>
              <strong>{formatDateTime(report?.generated_at)}</strong>
            </div>
          </div>

          <div className="conclusion-card">
            <h3>审查结论摘要</h3>
            <p>{getReportConclusion(report)}</p>
          </div>

          <div className="report-list">
            <h3>问题摘要（前5条）</h3>
            {!report ? (
              <p className="empty-text">尚未生成报告。</p>
            ) : report.issue_list.length === 0 ? (
              <p className="empty-text">报告中暂无问题项。</p>
            ) : (
              <ul>
                {report.issue_list.slice(0, 5).map((item) => (
                  <li key={`${item.index}-${item.clause_reference}`}>
                    <div>
                      <p>{translateEnglishText(item.issue_description)}</p>
                      <small>
                        {getAuditGroupLabel(item.audit_group)} | {item.clause_reference} | 置信度{' '}
                        {Math.round(item.confidence * 100)}%
                      </small>
                    </div>
                    <span className={`severity-badge ${getSeverityClass(item.severity)}`}>
                      {getSeverityLabel(item.severity)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </main>
    </div>
  )
}

export default App
