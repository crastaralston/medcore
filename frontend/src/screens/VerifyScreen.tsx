import { useEffect, useState } from 'react'
import { api, ApiError, type VerifyResponse } from '../api'
import { Button, Card, ErrorBox, FilePicker, ScreenIntro } from '../components/ui'
import { fileTitle, formatTime, KIND_LABEL, SEAL_STEPS, SEAL_TONE, stepState, TONE_STYLE } from '../format'

/** Screen 2, for anyone: check one document's QR seal against the printed page. */
export function VerifyScreen() {
  const [samples, setSamples] = useState<string[]>([])
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<VerifyResponse | null>(null)

  useEffect(() => {
    api.listVerifySamples().then(setSamples).catch((e) => setError(e instanceof ApiError ? e.message : String(e)))
  }, [])

  const run = async (key: string, task: () => Promise<VerifyResponse>) => {
    setBusy(key)
    setError(null)
    try {
      setResult(await task())
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div>
      <ScreenIntro who="For anyone: employers, pharmacists, insurers" title="Check one document">
        Upload a document or a photo of it. MedCore reads the QR seal, checks the signature against the registry
        and the public log, then compares every signed fact with what is printed on the page.
      </ScreenIntro>
      <ErrorBox message={error} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Upload a document">
          <FilePicker file={file} onFile={setFile} accept=".pdf,.png,.jpg,.jpeg" hint="A PDF, or a photo or scan of the page" />
          <Button className="mt-4 w-full" busy={busy === 'upload'} disabled={!file || busy !== null}
                  onClick={() => file && run('upload', () => api.verify(file))}>
            Verify document
          </Button>
        </Card>
        <Card title="Or try a demo document">
          <div className="space-y-2">
            {samples.map((name) => (
              <button
                key={name}
                type="button"
                disabled={busy !== null}
                onClick={() => run(name, () => api.verifySample(name))}
                className="w-full rounded-xl border border-slate-200 px-4 py-2.5 text-left text-sm font-medium text-slate-800 hover:border-teal-600 hover:bg-teal-50 disabled:opacity-60"
              >
                {busy === name ? 'Checking...' : fileTitle(name)}
              </button>
            ))}
          </div>
        </Card>
      </div>

      {result && <VerifyResult result={result} />}
    </div>
  )
}

function VerifyResult({ result }: { result: VerifyResponse }) {
  const { seal } = result
  const tone = TONE_STYLE[SEAL_TONE[seal.status]]
  return (
    <div className="mt-6 space-y-4">
      <div className={`flex items-start gap-4 rounded-2xl border p-5 ${tone.card}`}>
        <span className={`mt-1.5 h-4 w-4 shrink-0 rounded-full ${tone.dot}`} aria-hidden />
        <div>
          <p className="text-2xl font-semibold">{seal.title}</p>
          <p className="mt-1 text-sm">{seal.detail}</p>
          <p className="mt-1 text-xs opacity-70">{result.file_name}</p>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <Card title="What was checked, in order">
          <ol className="space-y-2 text-sm">
            {SEAL_STEPS.map((step, i) => {
              const state = stepState(seal.status, i)
              const mark = state === 'pass' ? '✓' : state === 'fail' ? '✗' : '–'
              const style = state === 'pass' ? 'bg-emerald-100 text-emerald-800'
                : state === 'fail' ? 'bg-red-100 text-red-800' : 'bg-slate-100 text-slate-400'
              return (
                <li key={step.key} className="flex items-center gap-3">
                  <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${style}`}>{mark}</span>
                  <span className={state === 'skip' ? 'text-slate-400' : 'text-slate-800'}>{step.label}</span>
                </li>
              )
            })}
          </ol>
          {seal.text_matches !== null && seal.status !== 'no_seal' && (
            <p className="mt-3 text-xs text-slate-500">
              Rest of the page text: {seal.text_matches ? 'unchanged since sealing.' : 'changed since sealing.'}
            </p>
          )}
        </Card>

        {seal.issuer ? (
          <Card title="Who issued it">
            <p className="font-semibold text-slate-900">{seal.issuer.name}</p>
            <p className="text-sm text-slate-600">{KIND_LABEL[seal.issuer.kind]} · {seal.issuer.address}</p>
            <dl className="mt-3 grid grid-cols-[120px_1fr] gap-x-3 gap-y-1 text-sm">
              <dt className="text-slate-500">Key fingerprint</dt>
              <dd className="font-mono text-xs text-slate-800">{seal.issuer.key_fingerprint}</dd>
              {seal.sealed_at && (<><dt className="text-slate-500">Sealed</dt><dd>{formatTime(seal.sealed_at)}</dd></>)}
              {seal.stay_id && (<><dt className="text-slate-500">Hospital stay</dt><dd>{seal.stay_id}</dd></>)}
              {seal.log_entry && (<><dt className="text-slate-500">Public log</dt><dd>Entry #{seal.log_entry.seq}</dd></>)}
            </dl>
          </Card>
        ) : (
          <Card title="Who issued it">
            <p className="text-sm text-slate-600">
              {seal.status === 'no_seal'
                ? 'No seal, so the issuer cannot be confirmed. On the Claim check screen this document still gets the three content checks.'
                : 'The issuer could not be confirmed.'}
            </p>
          </Card>
        )}
      </div>

      {seal.fields.length > 0 && (
        <Card title="Signed facts compared with the printed page">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-slate-500">
                <tr>
                  <th className="py-2 pr-4 font-medium">Fact</th>
                  <th className="py-2 pr-4 font-medium">Signed by the issuer</th>
                  <th className="py-2 pr-4 font-medium">Printed on the page</th>
                  <th className="py-2 font-medium">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {seal.fields.map((f) => (
                  <tr key={f.field} className={f.status === 'different' ? 'bg-red-50' : ''}>
                    <td className="py-2 pr-4 text-slate-700">{f.label}</td>
                    <td className="py-2 pr-4 text-slate-900">{f.signed}</td>
                    <td className="py-2 pr-4 text-slate-900">{f.printed ?? 'could not read'}</td>
                    <td className="py-2 font-medium">
                      {f.status === 'match' ? <span className="text-emerald-700">Matches</span>
                        : f.status === 'different' ? <span className="text-red-700">Different</span>
                        : <span className="text-slate-500">Not read</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
