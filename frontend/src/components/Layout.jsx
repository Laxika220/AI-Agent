import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Menu } from 'lucide-react'
import Sidebar from './Sidebar'

export default function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="flex h-full">
      <div className="hidden md:block">
        <Sidebar />
      </div>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobileOpen(false)} />
          <div className="relative h-full w-60">
            <Sidebar onNavigate={() => setMobileOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-surface-border px-4 py-3 md:hidden">
          <button onClick={() => setMobileOpen(true)} className="btn-ghost p-1.5" aria-label="Open menu">
            <Menu className="h-5 w-5" />
          </button>
          <span className="text-sm font-semibold text-white">AgentForge</span>
        </header>
        <main className="scrollbar-thin flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
