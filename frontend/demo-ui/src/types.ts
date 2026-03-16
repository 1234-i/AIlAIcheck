export type PipelineStepKey = 'classify' | 'extract' | 'audit' | 'report'

export type StepStatus = 'idle' | 'running' | 'done' | 'failed'

export interface UploadResponse {
  batch_id: string
  file_ids: string[]
  status: string
}

export interface TriggerResponse {
  batch_id: string
  task_name: string
  status: string
}

export interface IssueEvidence {
  evidence_id: string
  source_file_id: string
  source_file_name: string
  page: number
  snippet: string
  locator: Record<string, unknown> | null
  field_path: string
  extracted_field_source: string
  rule_id: string
  clause_id: string
}

export interface AuditIssue {
  issue_id: string
  batch_id: string
  rule_id: string
  clause_id: string
  audit_group: string
  audit_object: string
  checkpoint: string
  result: string
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | string
  issue_description: string
  rectification_suggestion: string | null
  confidence: number
  evidence_chain: IssueEvidence[]
  contradiction_flags?: Record<string, unknown>
  review_status?: string
  review_comment?: string | null
  created_at?: string
  updated_at?: string
}

export interface IssuesResponse {
  items: AuditIssue[]
  total: number
  page: number
  page_size: number
}

export interface ReportItem {
  index: number
  audit_group: string
  audit_object: string
  checkpoint: string
  result: string
  issue_description: string
  clause_reference: string
  evidence_source: string
  severity: string
  rectification_suggestion: string | null
  confidence: number
  internal?: {
    triggered_rule?: string
    evidence_chain?: IssueEvidence[]
    [key: string]: unknown
  }
}

export interface AuditReport {
  report_id: string
  batch_id: string
  audit_version: string
  generated_at: string
  issue_list: ReportItem[]
  statistics: {
    total_issues: number
    critical: number
    high: number
    medium: number
    low: number
  }
  export_links: {
    json?: string
    excel?: string
    [key: string]: string | undefined
  }
  created_at?: string
  updated_at?: string
}

export interface StepRuntime {
  status: StepStatus
  durationMs?: number
  error?: string
}
