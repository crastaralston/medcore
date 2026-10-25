import { useRef, useState } from 'react'
import type { Sample } from '../api'
import { capitalise, sampleInfo } from '../format'

const ACCEPT = '.pdf,.png,.jpg,.jpeg,.webp,.tif,.tiff'
const MAX_FILES = 12

interface Props {
  samples: Sample[]
  busy: string | null
  onSample: (name: string) => void
  onUpload: (files: File[]) => void
}

/** Step 1: pick a ready-made sample claim, or upload the documents of a real one. */
export function ChooseClaim({ samples, busy, onSample, onUpload }: Props) {
  return (
    <div className="grid gap-4 md:grid-cols-[3fr_2fr]">
      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <h3 className="font-semibold text-slate-900">Use a sample claim</h3>
        <p className="mt-1 text-sm text-slate-500">
          Synthetic claim files made for testing: two genuine, the rest forged in different ways. The last three carry
          QR seals.
        </p>
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          {samples.map((s) => {
            const info = sampleInfo(s.name)
            const running = busy === s.name
            return (
              <button
                key={s.name}
                type="button"
                disabled={busy !== null}
                onClick={() => onSample(s.name)}
                className="rounded-xl border border-slate-200 px-4 py-3 text-left transition hover:border-teal-600 hover:bg-teal-50 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none disabled:opacity-60"
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="font-medium text-slate-900">{info.title}</span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      info.forged ? 'bg-red-50 text-red-700' : 'bg-emerald-50 text-emerald-700'
                    }`}
                  >
                    {info.forged ? 'Forged' : 'Genuine'}
                  </span>
                </span>
                <span className="mt-0.5 block text-xs text-slate-500">
                  {running
                    ? 'Checking...'
                    : `${capitalise(info.diagnosis)} · ${s.files.length} documents${s.sealed ? ' · sealed' : ''}`}
                </span>
              </button>
            )
          })}
        </div>
      </div>
      <UploadBox busy={busy === 'upload'} disabled={busy !== null} onUpload={onUpload} />
    </div>
  )
}

function UploadBox({ busy, disabled, onUpload }: { busy: boolean; disabled: boolean; onUpload: (f: File[]) => void }) {
  const [files, setFiles] = useState<File[]>([])
  const [dragging, setDragging] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  const add = (list: FileList | null) => {
    if (!list) return
    setFiles((prev) => {
      const names = new Set(prev.map((f) => f.name))
      return [...prev, ...Array.from(list).filter((f) => !names.has(f.name))].slice(0, MAX_FILES)
    })
  }

  return (
    <div className="flex flex-col rounded-2xl border border-slate-200 bg-white p-5">
      <h3 className="font-semibold text-slate-900">Or upload your own</h3>
      <p className="mt-1 text-sm text-slate-500">
        All documents of one claim: discharge summary, hospital bill, lab reports, pharmacy bill.
      </p>
      <button
        type="button"
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          add(e.dataTransfer.files)
        }}
        className={`mt-4 flex flex-1 flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-6 text-sm transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
          dragging ? 'border-teal-500 bg-teal-50' : 'border-slate-300 hover:border-slate-400'
        }`}
      >
        <span className="font-medium text-slate-700">Drop files or click to choose</span>
        <span className="mt-1 text-xs text-slate-500">PDF, PNG or JPG</span>
      </button>
      <input
        ref={input}
        type="file"
        multiple
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => {
          add(e.target.files)
          e.target.value = ''
        }}
      />
      {files.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm">
          {files.map((f) => (
            <li key={f.name} className="flex items-center justify-between gap-2">
              <span className="truncate text-slate-700">{f.name}</span>
              <button
                type="button"
                onClick={() => setFiles((prev) => prev.filter((x) => x !== f))}
                className="shrink-0 text-xs text-slate-500 hover:text-red-600"
                aria-label={`Remove ${f.name}`}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      <button
        type="button"
        disabled={disabled || files.length === 0}
        onClick={() => {
          onUpload(files)
          setFiles([])
        }}
        className="mt-4 rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-500"
      >
        {busy ? 'Checking...' : files.length ? `Check ${files.length} documents` : 'Check claim'}
      </button>
    </div>
  )
}
