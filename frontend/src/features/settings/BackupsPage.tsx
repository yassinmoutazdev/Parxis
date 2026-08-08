import { Link } from 'react-router-dom'
import { BackupsSection } from './components/BackupsSection'

export default function BackupsPage() {
  return (
    <div className="px-6 py-6 max-w-3xl mx-auto space-y-6">
      <div>
        <Link to="/settings" className="text-sm text-ink-muted hover:text-ink">
          ← Settings
        </Link>
        <h1 className="font-serif text-2xl text-ink mt-2">Backups</h1>
        <p className="text-sm text-ink-muted mt-1">
          Restore a previous snapshot of your data, or check when the last backup ran.
        </p>
      </div>

      <BackupsSection />
    </div>
  )
}