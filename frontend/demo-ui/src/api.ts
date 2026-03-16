import type {
  AuditReport,
  IssuesResponse,
  PipelineStepKey,
  TriggerResponse,
  UploadResponse,
} from './types'

const API_BASE = '/api/v1'

function extractErrorMessage(payload: unknown): string {
  if (typeof payload === 'string' && payload.trim().length > 0) {
    return payload
  }
  if (payload && typeof payload === 'object') {
    const detail = (payload as { detail?: unknown }).detail
    if (typeof detail === 'string') {
      return detail
    }
  }
  return '请求失败，请稍后重试。'
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  const contentType = response.headers.get('content-type') ?? ''

  let payload: unknown = null
  if (contentType.includes('application/json')) {
    payload = await response.json()
  } else {
    payload = await response.text()
  }

  if (!response.ok) {
    const message = extractErrorMessage(payload)
    throw new Error(`[${response.status}] ${message}`)
  }

  return payload as T
}

export async function uploadBatch(formData: FormData): Promise<UploadResponse> {
  return request<UploadResponse>(`${API_BASE}/batches/uploads`, {
    method: 'POST',
    body: formData,
  })
}

export async function triggerPipelineStep(
  batchId: string,
  step: PipelineStepKey,
): Promise<TriggerResponse> {
  return request<TriggerResponse>(`${API_BASE}/batches/${batchId}/${step}`, {
    method: 'POST',
  })
}

export async function fetchIssues(
  batchId: string,
  page = 1,
  pageSize = 50,
): Promise<IssuesResponse> {
  return request<IssuesResponse>(
    `${API_BASE}/batches/${batchId}/issues?page=${page}&page_size=${pageSize}`,
  )
}

export async function fetchReport(batchId: string): Promise<AuditReport> {
  return request<AuditReport>(`${API_BASE}/batches/${batchId}/report`)
}

export function getExcelDownloadUrl(batchId: string): string {
  return `${API_BASE}/batches/${batchId}/report.xlsx`
}
