import { useEffect, useMemo, useState } from 'react'
import {
  api, ApiError, sealedPdfUrl, sealedPreviewUrl, sealedQrUrl, type Issuer, type Sample, type SealResponse,
} from '../api'
import { Button, Card, ErrorBox, FilePicker, ScreenIntro } from '../components/ui'
import { DOC_TYPE_LABEL, FACT_LABELS, formatTime, KIND_LABEL, sampleInfo } from '../format'

/** Screen 1, for hospitals and labs: seal a document with a signed QR code. */
export function IssueScreen({ onVerify }: { onVerify: () => void }) {
  const [issuers, setIssuers] = useState<Issuer[]>([])
  const [samples, setSamples] = useState<Sample[]>([])
  const [issuerId, setIssuerId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [sampleFile, setSampleFile] = useState('')
  const [stayId, setStayId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<SealResponse | null>(null)

  useEffect(() => {
    Promise.all([api.listIssuers(), api.listSamples()])
      .then(([i, s]) => {
        const usable = i.filter((x) => x.status === 'active' && x.can_seal_here)
        setIssuers(usable)
        setIssuerId((current) => current || usable[0]?.id || '')
        setSamples(s.filter((x) => !x.sealed))
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : String(e)))
  }, [])

  const demoFiles = useMemo(
    () => samples.flatMap((s) => s.files.map((f) => ({ value: `${s.name}/${f}`, label: `${sampleInfo(s.name).title}: ${f}` }))),
    [samples],
  )

  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      const source = file ? { file } : { sampleFile }
      setResult(await api.seal(issuerId, stayId, source))
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <ScreenIntro who="For hospitals and labs" title="Seal a document before you print or send it">
        MedCore reads the document, signs its key facts with your hospital's private key, and stamps a QR code
        on the page. Every seal is also written to the public log. In a real hospital this runs on the hospital's
        own computer, so every document it prints is sealed.
      </ScreenIntro>
      <ErrorBox message={error} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="1. Who is sealing?">
          <label htmlFor="issuer" className="text-xs font-medium text-slate-600">Hospital, lab or pharmacy</label>
          <select
            id="issuer"
            value={issuerId}
            onChange={(e) => setIssuerId(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-teal-600 focus:outline-none"
          >
            {(['hospital', 'lab', 'pharmacy'] as const).map((kind) => (
              <optgroup key={kind} label={KIND_LABEL[kind]}>
                {issuers.filter((i) => i.kind === kind).map((i) => (
                  <option key={i.id} value={i.id}>{i.name}</option>
                ))}
              </optgroup>
            ))}
          </select>
          <label htmlFor="stay" className="mt-4 block text-xs font-medium text-slate-600">
            Hospital stay number (optional)
          </label>
          <input
            id="stay"
            value={stayId}
            onChange={(e) => setStayId(e.target.value)}
            placeholder="e.g. IPD/26/66701"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-teal-600 focus:outline-none"
          />
          <p className="mt-1 text-xs text-slate-500">
            Put the same number on every document of one stay. The claim check then catches a document that belongs
            to a different stay.
          </p>
        </Card>

        <Card title="2. Which document?">
          <FilePicker
            file={file}
            onFile={(f) => {
              setFile(f)
              if (f) setSampleFile('')
            }}
            accept=".pdf"
            hint="A PDF made by your hospital or lab software"
          />
          <label htmlFor="demo-file" className="mt-4 block text-xs font-medium text-slate-600">
            Or pick a demo document
          </label>
          <select
            id="demo-file"
            value={sampleFile}
            onChange={(e) => {
              setSampleFile(e.target.value)
              if (e.target.value) setFile(null)
            }}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-teal-600 focus:outline-none"
          >
            <option value="">Choose...</option>
            {demoFiles.map((f) => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
          <Button className="mt-4 w-full" busy={busy} disabled={!issuerId || (!file && !sampleFile)} onClick={submit}>
            Seal document
          </Button>
        </Card>
      </div>

      {result && <SealedResult result={result} onVerify={onVerify} />}
    </div>
  )
}

const DATE_LABEL: Record<string, string> = {
  lab_report: 'Reported on', hospital_bill: 'Bill date', pharmacy_bill: 'Invoice date',
}

function SealedResult({ result, onVerify }: { result: SealResponse; onVerify: () => void }) {
  const label = (key: string) => (key === 'doc_date' ? DATE_LABEL[result.payload.typ] : undefined) ?? FACT_LABELS[key] ?? key
  const facts = Object.entries(result.payload.f).flatMap(([key, value]) =>
    key === 'tests' && value && typeof value === 'object'
      ? Object.entries(value as Record<string, string>).map(([test, v]) => [capitalised(test), v] as const)
      : [[label(key), String(value)] as const],
  )
  return (
    <div className="mt-6 grid gap-4 lg:grid-cols-[320px_1fr]">
      <a href={sealedPdfUrl(result.doc_id, result.file_name)} target="_blank" rel="noreferrer" title="Open the sealed PDF">
        <img src={sealedPreviewUrl(result.doc_id)} alt="The sealed document, with its QR code bottom right"
             className="w-full rounded-2xl border border-slate-200 bg-white" />
      </a>
      <Card>
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-wide text-emerald-700 uppercase">Sealed</p>
            <p className="text-xl font-semibold text-slate-900">Seal ID {result.display_id}</p>
            <p className="mt-1 text-sm text-slate-600">
              {DOC_TYPE_LABEL[result.payload.typ] ?? result.payload.typ} sealed by {result.issuer.name} on{' '}
              {formatTime(result.payload.iat)}{result.payload.stay ? `, for stay ${result.payload.stay}` : ''}.
            </p>
          </div>
          <img src={sealedQrUrl(result.doc_id)} alt="The QR code printed on the document" className="h-28 w-28 shrink-0" />
        </div>
        <h4 className="mt-4 text-sm font-semibold text-slate-900">What the QR code signs</h4>
        <dl className="mt-2 grid grid-cols-[150px_1fr] gap-x-3 gap-y-1 text-sm">
          {facts.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-slate-500">{k}</dt>
              <dd className="text-slate-900">{v}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 text-xs text-slate-500">
          The seal also signs a fingerprint of all the text on the page, so any later edit is caught.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <a href={sealedPdfUrl(result.doc_id, result.file_name)} download={result.file_name}
             className="rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-800">
            Download sealed PDF
          </a>
          <button type="button" onClick={onVerify}
                  className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50">
            Next: verify it
          </button>
        </div>
      </Card>
    </div>
  )
}

function capitalised(s: string): string {
  return s.replace(/\b(ns1|igm|wbc|usg|ct)\b/gi, (m) => m.toUpperCase()).replace(/^./, (c) => c.toUpperCase())
}
