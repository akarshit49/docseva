//genai: Sprint 4 / WS-I — /library landing. Redirects to /library/formats.
import { redirect } from 'next/navigation'

export default function LibraryIndex() {
  redirect('/library/formats')
}
