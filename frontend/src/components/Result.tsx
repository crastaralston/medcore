import type { Check, Doc, Flag } from '../api'
import { fileUrl, previewUrl } from '../api'
import {
  CHECKS, displayLabel, formatDate, formatMoney, plural, SEAL_TONE, SEVERITY, TONE_STYLE, VERDICT,
} from '../format'

/** Step 2: the verdict, the three checks, every problem found, and what was read. */
export function Result({ check }: { check: Check }) {
  const { report } = check
  const verdict = VERDICT[report.verdict]
  const problems = report.flags.length

  return (
    <div className="space-y-4">
      <div className={`flex items-start gap-4 rounded-2xl border p-5 ${verdict.card}`}>
        <span className={`mt-1 h-4 w-4 shrink-0 rounded-full ${verdict.icon}`} aria-hidden />
        <div>
          <p className="text-2xl font-semibold">{verdict.title}</p>
          <p className="mt-1 text-sm">
            {problems === 0
              ? `All ${plural(report.documents.length, 'document')} agree with each other and with the diagnosis.`
              : `Found ${plural(problems, 'problem')} in ${plural(report.documents.length, 'document')}.`}{' '}
            <span className="opacity-70">{displayLabel(check.label)}</span>
          </p>
        </div>
      </div>

      {check.truth && <AnswerKey check={check} />}

      <div className="grid gap-3 sm:grid-cols-3">
        {CHECKS.map((c) => {
          const n = report.flags.filter((f) => f.checker === c.id).length
          return (
            <div key={c.id} className="rounded-2xl border border-slate-200 bg-white p-4">
              <p className="text-xs font-medium text-slate-500">Check {c.id}</p>
              <p className="font-semibold text-slate-900">{c.name}</p>
              <p className="mt-1 text-xs text-slate-500">{c.question}</p>
              <p className={`mt-2 text-sm font-semibold ${n ? 'text-red-700' : 'text-emerald-700'}`}>
                {n ? plural(n, 'problem') : 'No problems'}
              </p>
            </div>
          )
        })}
      </div>

      {problems > 0 && (
        <section className="rounded-2xl border border-slate-200 bg-white p-5">
          <h3 className="font-semibold text-slate-900">What we found</h3>
          <ol className="mt-3 space-y-3">
            {report.flags.map((f, i) => (
              <Problem key={`${f.code}-${i}`} flag={f} />
            ))}
          </ol>
        </section>
      )}

      {report.notes.length > 0 && (
        <section className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-600">
          <h3 className="font-semibold text-slate-900">Not checked in this version</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {report.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </section>
      )}

      <details className="group rounded-2xl border border-slate-200 bg-white p-5">
        <summary className="cursor-pointer font-semibold text-slate-900 marker:text-slate-400">
          What we read from each document ({report.documents.length})
        </summary>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {report.documents.map((d) => (
            <DocumentCard key={d.file_name} checkId={check.id} doc={d} />
          ))}
        </div>
      </details>
    </div>
  )
}

function AnswerKey({ check }: { check: Check }) {
  const truth = check.truth!
  const held = check.verdict === 'hold'
  const right = truth.genuine !== held
  const outcome = truth.genuine
    ? held ? 'False alarm: a genuine claim was held.' : 'Correct: the genuine claim passed.'
    : held ? 'Caught: the forgery was held for review.' : 'Missed: this forgery got through. This is a known gap.'
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <p className="text-xs font-medium text-slate-500">Answer key for this sample</p>
      <p className="mt-1 text-slate-900">
        {truth.genuine ? 'Nothing was changed. This is a genuine claim.' : `What was faked: ${truth.description}.`}
      </p>
      <p className={`mt-2 text-sm font-semibold ${right ? 'text-emerald-700' : 'text-red-700'}`}>{outcome}</p>
    </div>
  )
}

function Problem({ flag }: { flag: Flag }) {
  const severity = SEVERITY[flag.severity]
  const evidence = flag.evidence.filter(Boolean)
  return (
    <li className="rounded-xl border border-slate-200 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${severity.style}`}>{severity.word}</span>
        <span className="font-semibold text-slate-900">{flag.title}</span>
      </div>
      <p className="mt-1.5 text-sm text-slate-700">{flag.detail}</p>
      <p className="mt-2 text-xs text-slate-500">
        Found by check {flag.checker} ({CHECKS[flag.checker - 1].name}) in {flag.documents.join(', ')}
      </p>
      {evidence.length > 0 && (
        <details className="mt-2 text-xs">
          <summary className="cursor-pointer text-teal-700">Show the exact text</summary>
          <ul className="mt-2 space-y-1">
            {evidence.map((e, i) => (
              <li key={i} className="rounded-md bg-slate-50 px-2 py-1 font-mono break-words text-slate-700">
                {e}
              </li>
            ))}
          </ul>
        </details>
      )}
    </li>
  )
}

function DocumentCard({ checkId, doc }: { checkId: string; doc: Doc }) {
  const rows: [string, string][] = []
  const add = (label: string, value: string | null | undefined) => {
    if (value) rows.push([label, value])
  }
  add('Patient', doc.patient_name && [doc.patient_name, doc.age, doc.sex].filter(Boolean).join(', '))
  add('Issued by', doc.hospital ?? doc.lab_name)
  add('Doctor', doc.doctor)
  add('Admitted', formatDate(doc.admission))
  add('Discharged', formatDate(doc.discharge))
  add('Sample taken', formatDate(doc.collected))
  add('Dated', formatDate(doc.doc_date))
  add('Diagnosis', doc.diagnosis)
  add('Procedure', doc.procedure)
  add('Tests', doc.tests.map((t) => `${t.raw_name}: ${t.value}`).join('; '))
  add('Total', formatMoney(doc.total))

  return (
    <article className="overflow-hidden rounded-xl border border-slate-200">
      <a href={fileUrl(checkId, doc.file_name)} target="_blank" rel="noreferrer" title="Open the original file">
        <img
          src={previewUrl(checkId, doc.file_name)}
          alt={`First page of ${doc.file_name}`}
          className="h-44 w-full bg-slate-100 object-cover object-top"
          loading="lazy"
        />
      </a>
      <div className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="font-semibold text-slate-900">{doc.doc_type_label}</p>
            <p className="text-xs text-slate-500">{doc.file_name}</p>
          </div>
          {doc.seal && (
            <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${TONE_STYLE[SEAL_TONE[doc.seal.status]].pill}`}>
              {doc.seal.status === 'genuine' ? 'Sealed ✓' : doc.seal.status === 'no_seal' ? 'Not sealed' : doc.seal.title}
            </span>
          )}
        </div>
        <dl className="mt-2 grid grid-cols-[96px_1fr] gap-x-2 gap-y-1 text-xs">
          {rows.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-slate-500">{k}</dt>
              <dd className="break-words text-slate-800">{v}</dd>
            </div>
          ))}
        </dl>
      </div>
    </article>
  )
}
