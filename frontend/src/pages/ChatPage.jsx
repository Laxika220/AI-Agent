import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Bot, MessageSquare, Plus, Trash2 } from 'lucide-react'
import api from '../api/client'
import { useAgents } from '../hooks/useAgents'
import ChatInterface from '../components/ChatInterface'
import { EmptyState, Spinner, formatRelative } from '../components/ui'

export default function ChatPage() {
  const { agentId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const { agents, loading } = useAgents()
  const [conversations, setConversations] = useState([])

  const conversationId = searchParams.get('c')
  const agent = agents.find((a) => a.id === agentId)

  // Default to the first agent when none is selected.
  useEffect(() => {
    if (!agentId && agents.length) navigate(`/chat/${agents[0].id}`, { replace: true })
  }, [agentId, agents, navigate])

  const loadConversations = useCallback(() => {
    if (!agentId) return
    api
      .get('/chat/conversations', { params: { agent_id: agentId } })
      .then(({ data }) => setConversations(data))
      .catch(() => setConversations([]))
  }, [agentId])

  useEffect(loadConversations, [loadConversations])

  const selectConversation = (id) => setSearchParams(id ? { c: id } : {})

  const handleCreated = useCallback(
    (id) => {
      setSearchParams({ c: id }, { replace: true })
      loadConversations()
    },
    [setSearchParams, loadConversations],
  )

  const deleteConversation = async (id) => {
    await api.delete(`/chat/conversations/${id}`)
    if (id === conversationId) selectConversation(null)
    loadConversations()
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-slate-500">
        <Spinner className="h-6 w-6" />
      </div>
    )
  }

  if (!agents.length) {
    return (
      <div className="mx-auto max-w-xl px-4 py-16">
        <EmptyState
          icon={Bot}
          title="No agents to chat with"
          description="Create an agent first, then come back here to talk to it."
          action={<Link to="/agents" className="btn-primary">Create an agent</Link>}
        />
      </div>
    )
  }

  return (
    <div className="flex h-full">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-surface-border lg:flex">
        <div className="space-y-3 border-b border-surface-border p-3">
          <select
            className="input"
            value={agentId || ''}
            onChange={(e) => navigate(`/chat/${e.target.value}`)}
            aria-label="Select agent"
          >
            {agents.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
          <button onClick={() => selectConversation(null)} className="btn-secondary w-full">
            <Plus className="h-4 w-4" /> New chat
          </button>
        </div>
        <ul className="scrollbar-thin flex-1 space-y-0.5 overflow-y-auto p-2">
          {conversations.map((c) => (
            <li key={c.id} className="group relative">
              <button
                onClick={() => selectConversation(c.id)}
                className={`flex w-full items-start gap-2 rounded-lg px-3 py-2 pr-8 text-left text-sm ${
                  c.id === conversationId ? 'bg-surface-overlay text-white' : 'text-slate-400 hover:bg-surface-overlay/60'
                }`}
              >
                <MessageSquare className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{c.title}</span>
                  <span className="text-[11px] text-slate-600">{formatRelative(c.updated_at)}</span>
                </span>
              </button>
              <button
                onClick={() => deleteConversation(c.id)}
                className="absolute right-2 top-2 hidden text-slate-500 hover:text-red-400 group-hover:block"
                aria-label="Delete conversation"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
          {!conversations.length && <li className="px-3 py-2 text-xs text-slate-600">No conversations yet</li>}
        </ul>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-3 border-b border-surface-border px-4 py-3 sm:px-8">
          <select
            className="input w-auto lg:hidden"
            value={agentId || ''}
            onChange={(e) => navigate(`/chat/${e.target.value}`)}
            aria-label="Select agent"
          >
            {agents.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
          {agent && (
            <div className="hidden min-w-0 lg:block">
              <p className="truncate text-sm font-semibold text-white">{agent.name}</p>
              <p className="text-xs text-slate-500">
                {[...agent.tools, ...(agent.knowledge_base_id ? ['knowledge base'] : [])].join(' · ') || 'no tools'}
              </p>
            </div>
          )}
          <button onClick={() => selectConversation(null)} className="btn-ghost ml-auto lg:hidden">
            <Plus className="h-4 w-4" /> New
          </button>
        </div>
        <div className="min-h-0 flex-1">
          {agent && (
            <ChatInterface
              key={agent.id}
              agent={agent}
              conversationId={conversationId}
              onConversationCreated={handleCreated}
            />
          )}
        </div>
      </div>
    </div>
  )
}
