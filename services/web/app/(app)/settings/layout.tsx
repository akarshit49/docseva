//genai: Sprint 4 / WS-I — /settings layout (tab nav + content area).
import { SettingsTabs } from '@/components/shared/settings-tabs'

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-ink-900">Settings</h1>
        <p className="text-sm text-ink-500">Your organization preferences live here.</p>
      </div>
      <div className="flex flex-col gap-6 lg:flex-row">
        <SettingsTabs />
        <section className="flex-1">{children}</section>
      </div>
    </div>
  )
}
