export type Severity = 'high' | 'medium' | 'low'
export type Verdict = 'hold' | 'pass_with_notes' | 'pass'

export interface Flag {
  checker: 1 | 2 | 3
  checker_name: string
  code: string
  severity: Severity
  title: string
  detail: string
  documents: string[]
  evidence: string[]
}

export interface LabTest {
  name: string
  raw_name: string
  value: string
  unit: string
}

export interface LineItem {
  description: string
  qty: number | null
  rate: number | null
  amount: number | null
}

export type IssuerKind = 'hospital' | 'lab' | 'pharmacy'

export interface Issuer {
  id: string
  name: string
  kind: IssuerKind
  address: string
  status: 'active' | 'suspended'
  key_fingerprint: string
  created_at: string
  documents_sealed: number
  can_seal_here?: boolean
}

export type SealStatus =
  | 'genuine' | 'altered' | 'revoked' | 'unlogged' | 'bad_signature' | 'unknown_issuer' | 'unreadable' | 'no_seal'

export interface FieldCheck {
  field: string
  label: string
  signed: string
  printed: string | null
  status: 'match' | 'different' | 'unreadable'
}

export interface LogEntry {
  seq: number
  kind: 'seal' | 'revoke'
  doc_id: string
  display_id?: string
  issuer_id: string
  issuer?: string
  doc_type: string
  stay_id: string | null
  created_at: string
  reason: string | null
  payload_hash: string
  entry_hash: string
}

export interface SealCheck {
  status: SealStatus
  title: string
  detail: string
  doc_id: string | null
  issuer: Issuer | null
  sealed_at: string | null
  stay_id: string | null
  doc_type: string | null
  fields: FieldCheck[]
  text_matches: boolean | null
  log_entry: LogEntry | null
  revocation: LogEntry | null
}

export interface SealResponse {
  doc_id: string
  display_id: string
  payload: { iss: string; typ: string; iat: string; stay: string | null; f: Record<string, unknown> }
  document: Doc
  issuer: Issuer
  file_name: string
}

export interface VerifyResponse {
  file_name: string
  seal: SealCheck
  document: Doc
}

export interface Alert {
  rule: string
  issuer_id: string
  issuer: string
  title: string
  detail: string
}

export interface LogResponse {
  intact: boolean
  broken_at: number[]
  alerts: Alert[]
  entries: LogEntry[]
}

export interface Doc {
  seal: SealCheck | null
  file_name: string
  doc_type: string
  doc_type_label: string
  patient_name: string | null
  age: number | null
  sex: string | null
  hospital: string | null
  lab_name: string | null
  doctor: string | null
  admission: string | null
  discharge: string | null
  collected: string | null
  doc_date: string | null
  diagnosis: string | null
  procedure: string | null
  tests: LabTest[]
  items: LineItem[]
  total: number | null
}

export interface Report {
  verdict: Verdict
  verdict_label: string
  flags: Flag[]
  documents: Doc[]
  notes: string[]
  seconds: number
}

export interface Truth {
  genuine: boolean
  forgery_type: string | null
  variant: string | null
  changed_document: string | null
  description: string
  diagnosis: string
}

export interface CheckSummary {
  id: string
  created_at: string
  label: string
  verdict: Verdict
  flag_count: number
  patient_name: string | null
  file_names: string[]
}

export interface Check extends CheckSummary {
  report: Report
  truth: Truth | null
}

export interface Sample {
  name: string
  diagnosis: string | null
  sealed: boolean
  files: string[]
}

export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, init)
  } catch {
    throw new ApiError('Cannot reach the MedCore Verify server. Is it running on port 8000?')
  }
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      /* not JSON */
    }
    throw new ApiError(message)
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T)
}

export const api = {
  health: () => request<{ status: string; image_ocr: boolean; admin_locked: boolean }>('/api/health'),
  listChecks: () => request<CheckSummary[]>('/api/checks'),
  getCheck: (id: string) => request<Check>(`/api/checks/${id}`),
  deleteCheck: (id: string) => request<void>(`/api/checks/${id}`, { method: 'DELETE' }),
  listSamples: () => request<Sample[]>('/api/samples'),
  checkSample: (name: string) =>
    request<Check>(`/api/samples/${encodeURIComponent(name)}/check`, { method: 'POST' }),
  upload: (files: File[], label: string) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    form.append('label', label)
    return request<Check>('/api/checks', { method: 'POST', body: form })
  },

  listIssuers: () => request<Issuer[]>('/api/issuers'),
  addIssuer: (name: string, kind: IssuerKind, address: string) =>
    request<Issuer>('/api/issuers', json({ name, kind, address })),
  setIssuerStatus: (id: string, status: Issuer['status']) =>
    request<Issuer>(`/api/issuers/${encodeURIComponent(id)}/status`, json({ status })),

  seal: (issuerId: string, stayId: string, source: { file: File } | { sampleFile: string }) => {
    const form = new FormData()
    form.append('issuer_id', issuerId)
    form.append('stay_id', stayId)
    if ('file' in source) form.append('file', source.file)
    else form.append('sample_file', source.sampleFile)
    return request<SealResponse>('/api/seal', { method: 'POST', body: form })
  },

  verify: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<VerifyResponse>('/api/verify', { method: 'POST', body: form })
  },
  listVerifySamples: () => request<string[]>('/api/verify-samples'),
  verifySample: (name: string) =>
    request<VerifyResponse>(`/api/verify-samples/${encodeURIComponent(name)}`, { method: 'POST' }),

  log: () => request<LogResponse>('/api/log'),
  revoke: (docId: string, reason: string) =>
    request<LogEntry>(`/api/log/${encodeURIComponent(docId)}/revoke`, json({ reason })),
}

let adminToken = ''

/** On a public deployment, registry changes need the admin token; it is kept in memory only. */
export function setAdminToken(token: string) {
  adminToken = token.trim()
}

function json(body: unknown): RequestInit {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (adminToken) headers['X-Admin-Token'] = adminToken
  return { method: 'POST', headers, body: JSON.stringify(body) }
}

export const sealedPdfUrl = (docId: string, fileName: string) =>
  `/api/sealed/${docId}.pdf?name=${encodeURIComponent(fileName)}`
export const sealedQrUrl = (docId: string) => `/api/sealed/${docId}/qr.png`
export const sealedPreviewUrl = (docId: string) => `/api/sealed/${docId}/preview.png`

export const previewUrl = (checkId: string, fileName: string) =>
  `/api/checks/${checkId}/previews/${encodeURIComponent(fileName)}`
export const fileUrl = (checkId: string, fileName: string) =>
  `/api/checks/${checkId}/files/${encodeURIComponent(fileName)}`
