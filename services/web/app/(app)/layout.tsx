//genai: Sprint 3 / WS-G — protected app layout (sidebar + topbar + content).
//
// `requireMe()` (server) redirects to /login if the cookie is missing or the
// API rejects the JWT, so client components in this group can safely assume
// the user is authenticated.
import { SidebarNav } from '@/components/shared/sidebar-nav'
import { TopBar } from '@/components/shared/top-bar'
import { requireMe } from '@/lib/auth'

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const me = await requireMe()
  return (
    <div className="flex min-h-screen bg-ink-100/40">
      <SidebarNav />
      <div className="flex flex-1 flex-col">
        <TopBar
          orgName={me.organization.name}
          userName={me.user.name}
          quotaUsed={me.organization.docs_used_this_cycle}
          quotaLimit={me.organization.docs_limit_per_cycle}
          plan={me.organization.plan}
        />
        <main className="flex-1 px-4 py-8 lg:px-8">{children}</main>
      </div>
    </div>
  )
}
