import { useRef, useState, type ReactNode } from 'react'

/** The line at the top of every screen: who uses it, and what it does. */
export function ScreenIntro({ who, title, children }: { who: string; title: string; children: ReactNode }) {
  return (
    <div className="mb-6">
      <p className="text-xs font-semibold tracking-wide text-teal-700 uppercase">{who}</p>
      <h2 className="mt-1 text-2xl font-semibold text-slate-900">{title}</h2>
      <p className="mt-2 max-w-3xl text-sm text-slate-600">{children}</p>
    </div>
  )
}

export function Card({ title, children, className = '' }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-slate-200 bg-white p-5 ${className}`}>
      {title && <h3 className="mb-3 font-semibold text-slate-900">{title}</h3>}
      {children}
    </section>
  )
}

export function ErrorBox({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <div role="alert" className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      {message}
    </div>
  )
}

export function Button({ children, busy, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { busy?: boolean }) {
  return (
    <button
      type="button"
      {...props}
      disabled={props.disabled || busy}
      className={`rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-800 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-500 ${props.className ?? ''}`}
    >
      {busy ? 'Working...' : children}
    </button>
  )
}

/** A drop zone for one file. */
export function FilePicker({ file, onFile, accept, hint }: {
  file: File | null
  onFile: (f: File | null) => void
  accept: string
  hint: string
}) {
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  return (
    <div>
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
          if (e.dataTransfer.files[0]) onFile(e.dataTransfer.files[0])
        }}
        className={`flex w-full flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-6 text-sm transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
          dragging ? 'border-teal-500 bg-teal-50' : 'border-slate-300 hover:border-slate-400'
        }`}
      >
        <span className="font-medium text-slate-700">{file ? file.name : 'Drop a file or click to choose'}</span>
        <span className="mt-1 text-xs text-slate-500">{file ? 'Click to choose a different file' : hint}</span>
      </button>
      <input
        ref={input}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          onFile(e.target.files?.[0] ?? null)
          e.target.value = ''
        }}
      />
    </div>
  )
}

export function Pill({ children, className }: { children: ReactNode; className: string }) {
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${className}`}>{children}</span>
}
