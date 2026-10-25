import type { IssuerKind, SealStatus, Severity, Verdict } from './api'

export function formatDate(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso)
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('en-IN', {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  })
}

export function formatMoney(n: number | null): string {
  if (n === null) return ''
  return `₹${n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

export function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

/** A check's label as people should read it: 'Sample: 02_edited_lab_value_dengue' -> 'Sample: Lab value edited (dengue)'. */
export function displayLabel(label: string): string {
  if (!label.startsWith('Sample: ')) return label
  const info = sampleInfo(label.slice('Sample: '.length))
  return `Sample: ${info.title} (${info.diagnosis})`
}

const SAMPLE_TITLES: Record<string, { title: string; forged: boolean }> = {
  genuine: { title: 'Genuine claim', forged: false },
  edited_lab_value: { title: 'Lab value edited', forged: true },
  upgraded_diagnosis: { title: 'Diagnosis upgraded', forged: true },
  painted_over_total: { title: 'Bill total painted over', forged: true },
  padded_room_days: { title: 'Extra room days billed', forged: true },
  tripled_pharmacy_qty: { title: 'Pharmacy quantities tripled', forged: true },
  sealed_genuine: { title: 'Sealed genuine claim', forged: false },
  sealed_then_edited: { title: 'Edited after sealing', forged: true },
  borrowed_sealed_report: { title: 'Sealed report from another stay', forged: true },
}

/** '02_edited_lab_value_dengue' -> { title: 'Lab value edited', diagnosis: 'dengue', forged: true } */
export function sampleInfo(name: string): { title: string; diagnosis: string; forged: boolean } {
  const parts = name.replace(/^\d+_/, '').split('_')
  const diagnosis = parts.pop() ?? ''
  const known = SAMPLE_TITLES[parts.join('_')]
  return { title: known?.title ?? parts.join(' '), forged: known?.forged ?? true, diagnosis }
}

export const VERDICT: Record<Verdict, { title: string; card: string; icon: string }> = {
  hold: { title: 'Hold for review', card: 'border-red-200 bg-red-50 text-red-900', icon: 'bg-red-600' },
  pass_with_notes: {
    title: 'Probably fine, with notes',
    card: 'border-amber-200 bg-amber-50 text-amber-900',
    icon: 'bg-amber-500',
  },
  pass: { title: 'No problems found', card: 'border-emerald-200 bg-emerald-50 text-emerald-900', icon: 'bg-emerald-600' },
}

export const SEVERITY: Record<Severity, { word: string; style: string }> = {
  high: { word: 'Serious', style: 'bg-red-100 text-red-800' },
  medium: { word: 'Check', style: 'bg-amber-100 text-amber-900' },
  low: { word: 'Minor', style: 'bg-slate-100 text-slate-700' },
}

export const CHECKS = [
  { id: 1, name: 'Seals and editing signs', question: 'Is each QR seal valid and true to its page? Was any file edited?' },
  { id: 2, name: 'Documents agree', question: 'Do names, dates, amounts and lab values match across documents?' },
  { id: 3, name: 'Medicine fits', question: 'Does the diagnosis match the tests, results, drugs and charges?' },
] as const

export type Tone = 'good' | 'bad' | 'warn' | 'neutral'

export const TONE_STYLE: Record<Tone, { card: string; pill: string; dot: string }> = {
  good: { card: 'border-emerald-200 bg-emerald-50 text-emerald-900', pill: 'bg-emerald-100 text-emerald-800', dot: 'bg-emerald-600' },
  bad: { card: 'border-red-200 bg-red-50 text-red-900', pill: 'bg-red-100 text-red-800', dot: 'bg-red-600' },
  warn: { card: 'border-amber-200 bg-amber-50 text-amber-900', pill: 'bg-amber-100 text-amber-900', dot: 'bg-amber-500' },
  neutral: { card: 'border-slate-200 bg-slate-50 text-slate-800', pill: 'bg-slate-100 text-slate-700', dot: 'bg-slate-400' },
}

export const SEAL_TONE: Record<SealStatus, Tone> = {
  genuine: 'good',
  altered: 'bad',
  revoked: 'bad',
  unlogged: 'bad',
  bad_signature: 'bad',
  unknown_issuer: 'bad',
  unreadable: 'warn',
  no_seal: 'neutral',
}

/** The checks Verify runs, in order. A seal status says where the chain stopped. */
export const SEAL_STEPS = [
  { key: 'found', label: 'A MedCore QR seal is on the page' },
  { key: 'issuer', label: 'The issuer is in the registry' },
  { key: 'signature', label: "The signature is the issuer's" },
  { key: 'logged', label: 'The seal is in the public log' },
  { key: 'revoked', label: 'The issuer has not revoked it' },
  { key: 'matches', label: 'Every signed fact matches the page' },
] as const

const FAILS_AT: Record<SealStatus, number> = {
  no_seal: 0, unreadable: 0, unknown_issuer: 1, bad_signature: 2, unlogged: 3, revoked: 4, altered: 5, genuine: 6,
}

export function stepState(status: SealStatus, index: number): 'pass' | 'fail' | 'skip' {
  const failsAt = FAILS_AT[status]
  if (index < failsAt) return 'pass'
  return index === failsAt ? 'fail' : 'skip'
}

export const FACT_LABELS: Record<string, string> = {
  patient_name: 'Patient name', age: 'Age', sex: 'Sex', admission: 'Admission date', discharge: 'Discharge date',
  collected: 'Sample collected', doc_date: 'Document date', diagnosis: 'Diagnosis', procedure: 'Procedure',
  total: 'Total amount',
}

export const DOC_TYPE_LABEL: Record<string, string> = {
  discharge_summary: 'Discharge summary', hospital_bill: 'Hospital bill', lab_report: 'Lab report',
  pharmacy_bill: 'Pharmacy bill', prescription: 'Prescription', unknown: 'Document',
}

export const KIND_LABEL: Record<IssuerKind, string> = { hospital: 'Hospital', lab: 'Laboratory', pharmacy: 'Pharmacy' }

/** '2_edited_after_sealing.pdf' -> 'Edited after sealing' */
export function fileTitle(name: string): string {
  const words = name.replace(/\.pdf$/i, '').replace(/^\d+_/, '').replace(/_/g, ' ')
  return capitalise(words.replace(/\bqr\b/i, 'QR'))
}
