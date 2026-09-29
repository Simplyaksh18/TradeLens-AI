import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { X } from 'lucide-react'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { Footer } from './Footer'
import { NAV_GROUPS } from './navigation'

function currentPageTitle(pathname: string): string {
  for (const group of NAV_GROUPS) {
    const match = group.items.find((item) => (item.path === '/' ? pathname === '/' : pathname.startsWith(item.path)))
    if (match) return match.label
  }
  return 'TradeLens AI'
}

export function AppShell() {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const location = useLocation()

  return (
    <div className="flex h-full min-h-screen bg-[var(--surface-0)] text-[var(--text-primary)]">
      <div className="hidden lg:block">
        <Sidebar />
      </div>

      {drawerOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setDrawerOpen(false)} aria-hidden="true" />
          <div className="relative z-50">
            <Sidebar onNavigate={() => setDrawerOpen(false)} />
          </div>
          <button
            type="button"
            aria-label="Close navigation menu"
            className="absolute right-3 top-3 z-50 rounded p-1.5 text-white"
            onClick={() => setDrawerOpen(false)}
          >
            <X size={18} />
          </button>
        </div>
      )}

      <div className="flex min-h-screen flex-1 flex-col">
        <TopBar pageTitle={currentPageTitle(location.pathname)} onMenuClick={() => setDrawerOpen(true)} />
        <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>
        <Footer />
      </div>
    </div>
  )
}
