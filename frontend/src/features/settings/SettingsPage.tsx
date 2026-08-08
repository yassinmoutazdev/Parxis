import { Link } from 'react-router-dom'
import { ConfigSection } from './components/ConfigSection'
import { VaultPathSection } from './components/VaultPathSection'
import { Card, CardContent } from '../../shared/components/Card'

export default function SettingsPage() {
  return (
    <div className="px-6 py-6 max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="font-serif text-2xl text-ink">Settings</h1>
        <p className="text-sm text-ink-muted mt-1">
          Adjust how Praxis reviews things with you, and where it looks for your notes.
        </p>
      </div>

      <ConfigSection />
      <VaultPathSection />

      <Card>
        <CardContent className="flex items-center justify-between">
          <div>
            <h2 className="font-serif text-lg text-ink">Backups</h2>
            <p className="text-sm text-ink-muted mt-1">
              Restore a previous snapshot of your data.
            </p>
          </div>
          <Link
            to="/settings/backups"
            className="text-sm bg-cream-100 border border-border rounded-lg px-4 py-1.5 text-ink hover:bg-cream-200 shrink-0"
          >
            Manage backups
          </Link>
        </CardContent>
      </Card>
    </div>
  )
}
