//genai: Sprint 4 / WS-I — /settings index redirects to /settings/profile.
import { redirect } from 'next/navigation'

export default function SettingsIndex() {
  redirect('/settings/profile')
}
