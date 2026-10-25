import { useEffect, useState } from 'react'
import { ClaimScreen } from './screens/ClaimScreen'
import { IssueScreen } from './screens/IssueScreen'
import { RegistryScreen } from './screens/RegistryScreen'
import { VerifyScreen } from './screens/VerifyScreen'

const SCREENS = [
  { id: 'issue', n: 1, name: 'Issue', who: 'Hospital or lab' },
  { id: 'verify', n: 2, name: 'Verify', who: 'Anyone' },
  { id: 'claims', n: 3, name: 'Claim check', who: 'Insurer' },
  { id: 'registry', n: 4, name: 'Registry and log', who: 'Administrator' },
] as const

type ScreenId = (typeof SCREENS)[number]['id']

function screenFromHash(): ScreenId {
  const id = window.location.hash.replace('#', '')
  return SCREENS.some((s) => s.id === id) ? (id as ScreenId) : 'issue'
}

export default function App() {
  const [screen, setScreen] = useState<ScreenId>(screenFromHash)

  useEffect(() => {
    const onHash = () => setScreen(screenFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const go = (id: ScreenId) => {
    window.location.hash = id
    window.scrollTo({ top: 0 })
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <div className="flex items-center gap-3 py-4">
            <img src="/favicon.svg" alt="" className="h-9 w-9" />
            <div>
              <h1 className="text-xl font-semibold text-slate-900">MedCore</h1>
              <p className="text-sm text-slate-500">
                Hospitals seal documents with a signed QR code. Anyone can verify them. Insurers check every claim.
              </p>
            </div>
          </div>
          <nav aria-label="Screens" className="-mb-px flex gap-1 overflow-x-auto">
            {SCREENS.map((s) => {
              const active = s.id === screen
              return (
                <a
                  key={s.id}
                  href={`#${s.id}`}
                  aria-current={active ? 'page' : undefined}
                  className={`flex shrink-0 items-center gap-2 border-b-2 px-3 pt-2 pb-3 text-sm ${
                    active ? 'border-teal-700 text-slate-900' : 'border-transparent text-slate-500 hover:text-slate-800'
                  }`}
                >
                  <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${
                    active ? 'bg-teal-700 text-white' : 'bg-slate-100 text-slate-600'
                  }`}>{s.n}</span>
                  <span>
                    <span className="block font-semibold">{s.name}</span>
                    <span className="block text-xs text-slate-500">{s.who}</span>
                  </span>
                </a>
              )
            })}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        {screen === 'issue' && <IssueScreen onVerify={() => go('verify')} />}
        {screen === 'verify' && <VerifyScreen />}
        {screen === 'claims' && <ClaimScreen />}
        {screen === 'registry' && <RegistryScreen />}
      </main>

      <footer className="mx-auto max-w-6xl px-4 pb-8 text-xs text-slate-500 sm:px-6">
        A problem means "check this", never "fraud". This version reads PDF documents and covers three diagnoses:
        dengue, typhoid and acute appendicitis. All demo documents and demo keys are synthetic.
      </footer>
    </div>
  )
}
