import { useCallback, useEffect, useState } from 'react'
import { api, ApiError, setAdminToken, type Issuer, type IssuerKind, type LogResponse } from '../api'
import { Button, Card, ErrorBox, Pill, ScreenIntro } from '../components/ui'
import { DOC_TYPE_LABEL, formatTime, KIND_LABEL } from '../format'

/** Screen 4, for administrators: who may seal, and the public log of every seal. */
export function RegistryScreen() {
  const [issuers, setIssuers] = useState<Issuer[]>([])
  const [log, setLog] = useState<LogResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [locked, setLocked] = useState(false)
  const [token, setToken] = useState('')

  const load = useCallback(
    () => Promise.all([api.listIssuers(), api.log(), api.health()]).then(([i, l, h]) => {
      setIssuers(i)
      setLog(l)
      setLocked(h.admin_locked)
    }),
    [],
  )
  const refresh = useCallback(
    () => load().catch((e) => setError(e instanceof ApiError ? e.message : String(e))),
    [load],
  )

  useEffect(() => {
    load().catch((e) => setError(e instanceof ApiError ? e.message : String(e)))
  }, [load])

  const act = async (task: () => Promise<unknown>) => {
    setError(null)
    try {
      await task()
      await refresh()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    }
  }

  const revoked = new Set(log?.entries.filter((e) => e.kind === 'revoke').map((e) => e.doc_id))

  return (
    <div>
      <ScreenIntro who="For administrators" title="Who can seal, and every seal ever made">
        Only registered hospitals, labs and pharmacies can make a valid seal: the registry holds their public keys.
        The public log records every seal with no patient data, and each entry is chained to the one before, so
        editing or deleting any entry is detected.
      </ScreenIntro>
      <ErrorBox message={error} />

      {locked && (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <span>This is a public demo: registering, suspending and revoking need the admin token.</span>
          <input
            type="password"
            value={token}
            onChange={(e) => {
              setToken(e.target.value)
              setAdminToken(e.target.value)
            }}
            placeholder="Admin token"
            aria-label="Admin token"
            className="rounded-md border border-amber-300 bg-white px-2 py-1 text-sm"
          />
        </div>
      )}

      <div className="space-y-4">
        <Card title={`Registered issuers (${issuers.length})`}>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-slate-500">
                <tr>
                  <th className="py-2 pr-4 font-medium">Name</th>
                  <th className="py-2 pr-4 font-medium">Type</th>
                  <th className="py-2 pr-4 font-medium">Public key fingerprint</th>
                  <th className="py-2 pr-4 font-medium">Sealed</th>
                  <th className="py-2 pr-4 font-medium">Status</th>
                  <th className="py-2 font-medium" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {issuers.map((i) => (
                  <tr key={i.id}>
                    <td className="py-2 pr-4 font-medium text-slate-900">{i.name}</td>
                    <td className="py-2 pr-4 text-slate-600">{KIND_LABEL[i.kind]}</td>
                    <td className="py-2 pr-4 font-mono text-xs text-slate-600">{i.key_fingerprint}</td>
                    <td className="py-2 pr-4 text-slate-600">{i.documents_sealed}</td>
                    <td className="py-2 pr-4">
                      <Pill className={i.status === 'active' ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}>
                        {i.status === 'active' ? 'Active' : 'Suspended'}
                      </Pill>
                    </td>
                    <td className="py-2 text-right">
                      <button
                        type="button"
                        onClick={() => act(() => api.setIssuerStatus(i.id, i.status === 'active' ? 'suspended' : 'active'))}
                        className="text-xs font-medium text-teal-700 hover:underline"
                      >
                        {i.status === 'active' ? 'Suspend' : 'Re-activate'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <AddIssuer onAdd={(name, kind, address) => act(() => api.addIssuer(name, kind, address))} />
        </Card>

        {log && (
          <Card title="Public log">
            <div className={`rounded-xl border p-3 text-sm ${log.intact ? 'border-emerald-200 bg-emerald-50 text-emerald-900' : 'border-red-200 bg-red-50 text-red-900'}`}>
              {log.intact
                ? `Log intact: every hash in all ${log.entries.length} entries checks out.`
                : `Log broken at entry ${log.broken_at.join(', ')}: an entry was changed or deleted.`}
            </div>
            <div className="mt-3 rounded-xl border border-slate-200 p-3 text-sm">
              <p className="font-semibold text-slate-900">Issuing alerts</p>
              {log.alerts.length === 0 ? (
                <p className="mt-1 text-slate-600">
                  None. An alert appears when a hospital or lab seals unusually many documents in one hour, which can
                  mean a certificate mill or a stolen key.
                </p>
              ) : (
                log.alerts.map((a) => (
                  <p key={a.issuer_id} className="mt-1 text-red-800"><strong>{a.issuer}:</strong> {a.detail}</p>
                ))
              )}
            </div>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs text-slate-500">
                  <tr>
                    <th className="py-2 pr-3 font-medium">#</th>
                    <th className="py-2 pr-3 font-medium">When</th>
                    <th className="py-2 pr-3 font-medium">Event</th>
                    <th className="py-2 pr-3 font-medium">Seal ID</th>
                    <th className="py-2 pr-3 font-medium">Issuer</th>
                    <th className="py-2 pr-3 font-medium">Document</th>
                    <th className="py-2 pr-3 font-medium">Entry hash</th>
                    <th className="py-2 font-medium" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {log.entries.map((e) => (
                    <tr key={e.seq}>
                      <td className="py-2 pr-3 text-slate-500">{e.seq}</td>
                      <td className="py-2 pr-3 whitespace-nowrap text-slate-600">{formatTime(e.created_at)}</td>
                      <td className="py-2 pr-3">
                        {e.kind === 'seal'
                          ? <Pill className="bg-slate-100 text-slate-700">Sealed</Pill>
                          : <Pill className="bg-red-100 text-red-800" >Revoked</Pill>}
                      </td>
                      <td className="py-2 pr-3 font-mono text-xs whitespace-nowrap">{e.display_id}</td>
                      <td className="py-2 pr-3 text-slate-700">{e.issuer}</td>
                      <td className="py-2 pr-3 text-slate-700">
                        {DOC_TYPE_LABEL[e.doc_type] ?? e.doc_type}
                        {e.reason && <span className="block text-xs text-red-700">{e.reason}</span>}
                      </td>
                      <td className="py-2 pr-3 font-mono text-xs text-slate-500" title={e.entry_hash}>{e.entry_hash.slice(0, 12)}…</td>
                      <td className="py-2 text-right">
                        {e.kind === 'seal' && !revoked.has(e.doc_id) && (
                          <RevokeButton onRevoke={(reason) => act(() => api.revoke(e.doc_id, reason))} />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}

function AddIssuer({ onAdd }: { onAdd: (name: string, kind: IssuerKind, address: string) => Promise<void> }) {
  const [name, setName] = useState('')
  const [kind, setKind] = useState<IssuerKind>('hospital')
  const [address, setAddress] = useState('')
  const [busy, setBusy] = useState(false)
  return (
    <details className="mt-4 rounded-xl border border-slate-200 p-4">
      <summary className="cursor-pointer text-sm font-semibold text-slate-900">Register a new hospital, lab or pharmacy</summary>
      <p className="mt-2 text-xs text-slate-500">
        MedCore creates a key pair: the public key goes into this registry, the private key stays on this machine.
      </p>
      <div className="mt-3 grid gap-3 sm:grid-cols-[2fr_1fr_2fr_auto]">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" aria-label="Name"
               className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <select value={kind} onChange={(e) => setKind(e.target.value as IssuerKind)} aria-label="Type"
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <option value="hospital">Hospital</option>
          <option value="lab">Laboratory</option>
          <option value="pharmacy">Pharmacy</option>
        </select>
        <input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Address" aria-label="Address"
               className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <Button busy={busy} disabled={!name.trim()} onClick={async () => {
          setBusy(true)
          await onAdd(name, kind, address)
          setBusy(false)
          setName('')
          setAddress('')
        }}>
          Register
        </Button>
      </div>
    </details>
  )
}

function RevokeButton({ onRevoke }: { onRevoke: (reason: string) => void }) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="text-xs font-medium text-red-700 hover:underline">
        Revoke
      </button>
    )
  }
  return (
    <span className="flex items-center justify-end gap-2">
      <input autoFocus value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason"
             aria-label="Reason for revoking" className="w-36 rounded-md border border-slate-300 px-2 py-1 text-xs" />
      <button type="button" onClick={() => onRevoke(reason)} className="text-xs font-semibold text-red-700">Confirm</button>
      <button type="button" onClick={() => setOpen(false)} className="text-xs text-slate-500">Cancel</button>
    </span>
  )
}
