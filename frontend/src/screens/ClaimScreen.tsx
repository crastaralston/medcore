import { useEffect, useRef, useState } from 'react'
import { api, ApiError, type Check, type CheckSummary, type Sample } from '../api'
import { ChooseClaim } from '../components/ChooseClaim'
import { Result } from '../components/Result'
import { ErrorBox, ScreenIntro } from '../components/ui'
import { displayLabel, formatTime, VERDICT } from '../format'

/** Screen 3, for insurers: check a whole claim file. */
export function ClaimScreen() {
  const [samples, setSamples] = useState<Sample[]>([])
  const [history, setHistory] = useState<CheckSummary[]>([])
  const [current, setCurrent] = useState<Check | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const resultRef = useRef<HTMLElement>(null)

  useEffect(() => {
    Promise.all([api.listSamples(), api.listChecks()])
      .then(([s, h]) => {
        setSamples(s)
        setHistory(h)
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : String(e)))
  }, [])

  const run = async (key: string, task: () => Promise<Check>) => {
    setBusy(key)
    setError(null)
    try {
      setCurrent(await task())
      setHistory(await api.listChecks())
      requestAnimationFrame(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-8">
      <ScreenIntro who="For insurance claim officers" title="Check a whole claim file">
        Upload every document of one claim. Sealed documents are checked against their QR seals. Every document,
        sealed or not, then goes through three checks: editing signs, whether the documents agree, and whether the
        medicine fits the diagnosis.
      </ScreenIntro>
      <ErrorBox message={error} />

      <ChooseClaim
        samples={samples}
        busy={busy}
        onSample={(name) => run(name, () => api.checkSample(name))}
        onUpload={(files) => run('upload', () => api.upload(files, files[0]?.name ?? 'Uploaded claim'))}
      />

      <section ref={resultRef} className="scroll-mt-6">
        {current ? (
          <Result check={current} />
        ) : (
          <p className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-500">
            The result appears here: a verdict, the three checks, and every problem found, with the exact text it
            came from.
          </p>
        )}
      </section>

      {history.length > 0 && (
        <details className="rounded-2xl border border-slate-200 bg-white p-5">
          <summary className="cursor-pointer font-semibold text-slate-900">Earlier checks ({history.length})</summary>
          <ul className="mt-3 divide-y divide-slate-100 text-sm">
            {history.map((h) => (
              <li key={h.id}>
                <button
                  type="button"
                  onClick={() => run(`open-${h.id}`, () => api.getCheck(h.id))}
                  className="flex w-full items-center justify-between gap-3 py-2 text-left hover:text-teal-700"
                >
                  <span className="truncate">{displayLabel(h.label)}</span>
                  <span className="shrink-0 text-xs text-slate-500">
                    {VERDICT[h.verdict].title} · {formatTime(h.created_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
