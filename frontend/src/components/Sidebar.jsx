import { NavLink } from 'react-router-dom'
import { Bot, FileText, LayoutDashboard, LogOut, MessageSquare, Workflow } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/agents', label: 'Agents', icon: Bot },
  { to: '/chat', label: 'Chat', icon: MessageSquare },
  { to: '/documents', label: 'Documents', icon: FileText },
  { to: '/chains', label: 'Chains', icon: Workflow },
]

export default function Sidebar({ onNavigate }) {
  const { user, logout } = useAuth()

  return (
    <aside className="flex h-full w-60 flex-col border-r border-surface-border bg-surface-raised">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-400 to-brand-600 text-sm font-bold text-white">
          AF
        </div>
        <div>
          <p className="text-sm font-semibold text-white">AgentForge</p>
          <p className="text-[11px] text-slate-500">Multi-agent platform</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                isActive
                  ? 'bg-brand-600/15 font-medium text-brand-400'
                  : 'text-slate-400 hover:bg-surface-overlay hover:text-slate-100'
              }`
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-surface-border p-3">
        <div className="flex items-center gap-3 rounded-lg px-2 py-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-overlay text-xs font-semibold uppercase text-slate-300">
            {(user?.full_name || user?.email || '?').slice(0, 1)}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm text-slate-200">{user?.full_name || 'Account'}</p>
            <p className="truncate text-xs text-slate-500">{user?.email}</p>
          </div>
          <button onClick={logout} className="btn-ghost p-1.5" title="Log out" aria-label="Log out">
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  )
}
