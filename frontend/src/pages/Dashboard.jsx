import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Bot, BookOpen, FileText, MessageSquare, Workflow } from 'lucide-react'
import api, { getErrorMessage } from '../api/client'
import { useAuth } from '../hooks/useAuth'
import { ErrorBanner, PageHeader, Spinner, formatRelative } from '../components/ui'

function StatCard({ icon: Icon, label, value, to }) {
  return (
    <Link to={to} className="card group flex items-center gap-4 p-5 transition-colors hover:border-brand-600/50">
      <div className="rounded-lg bg-brand-600/15 p-2.5 text-brand-400">
        <Icon className="h-5 w-5" />
      </div>
      <div className="flex-1">
        <p className="text-2xl font-semibold text-white">{value}</p>
        <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      </div>
      <ArrowRight className="h-4 w-4 text-slate-600 transition-transform group-hover:translate-x-0.5 group-hover:text-brand-400" />
    </Link>
  )
}

function ServiceDot({ name, ok }) {
  return (
    <span className="flex items-center gap-1.5 text-xs text-slate-400">
      <span className={`h-2 w-2 rounded-full ${ok ? 'bg-emerald-400' : 'bg-red-400'}`} />
      {name}
    </span>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([
      api.get('/agents'),
      api.get('/documents'),
      api.get('/knowledge-bases'),
      api.get('/chains'),
      api.get('/chat/conversations', { params: { limit: 6 } }),
    ])
      .then(([agents, documents, kbs, chains, conversations]) =>
        setData({
          agents: agents.data,
          documents: documents.data,
          kbs: kbs.data,
          chains: chains.data,
          conversations: conversations.data,
        }),
      )
      .catch((err) => setError(getErrorMessage(err, 'Failed to load dashboard')))
    api.get('/health').then(({ data: h }) => setHealth(h)).catch(() => {})
  }, [])

  const agentName = (id) => data?.agents.find((a) => a.id === id)?.name || 'Agent'

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-8">
      <PageHeader
        title={`Hi${user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''} 👋`}
        description="Here's what's happening across your agents."
        actions={
          health && (
            <div className="flex gap-3 rounded-lg border border-surface-border px-3 py-2">
              {Object.entries(health.services).map(([name, ok]) => (
                <ServiceDot key={name} name={name} ok={ok} />
              ))}
            </div>
          )
        }
      />
      <ErrorBanner message={error} />

      {!data ? (
        !error && (
          <div className="flex justify-center py-20 text-slate-500">
            <Spinner className="h-6 w-6" />
          </div>
        )
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard icon={Bot} label="Agents" value={data.agents.length} to="/agents" />
            <StatCard icon={BookOpen} label="Knowledge bases" value={data.kbs.length} to="/documents" />
            <StatCard icon={FileText} label="Documents" value={data.documents.length} to="/documents" />
            <StatCard icon={Workflow} label="Chains" value={data.chains.length} to="/chains" />
          </div>

          <div className="mt-8 grid gap-6 lg:grid-cols-[2fr_1fr]">
            <section className="card p-5">
              <h2 className="mb-4 text-sm font-semibold text-white">Recent conversations</h2>
              {data.conversations.length === 0 ? (
                <p className="text-sm text-slate-500">No conversations yet. Start one from the Chat page.</p>
              ) : (
                <ul className="divide-y divide-surface-border">
                  {data.conversations.map((c) => (
                    <li key={c.id}>
                      <Link to={`/chat/${c.agent_id}?c=${c.id}`} className="flex items-center gap-3 py-3 hover:text-white">
                        <MessageSquare className="h-4 w-4 text-slate-500" />
                        <span className="flex-1 truncate text-sm text-slate-200">{c.title}</span>
                        <span className="hidden text-xs text-slate-500 sm:inline">{agentName(c.agent_id)}</span>
                        <span className="text-xs text-slate-600">{formatRelative(c.updated_at)}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="card p-5">
              <h2 className="mb-4 text-sm font-semibold text-white">Quick start</h2>
              <ol className="space-y-3 text-sm text-slate-400">
                {[
                  ['Create a knowledge base and upload documents', '/documents'],
                  ['Build an agent with tools and your knowledge base', '/agents'],
                  ['Chat and watch it call tools in real time', '/chat'],
                  ['Chain agents into a multi-step pipeline', '/chains'],
                ].map(([text, to], i) => (
                  <li key={to + i} className="flex gap-3">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-surface-overlay font-mono text-[11px] text-brand-400">{i + 1}</span>
                    <Link to={to} className="hover:text-slate-100">{text}</Link>
                  </li>
                ))}
              </ol>
            </section>
          </div>
        </>
      )}
    </div>
  )
}
