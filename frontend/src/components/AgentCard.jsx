import { Link } from 'react-router-dom'
import { BookOpen, Bot, MessageSquare, Pencil, Trash2 } from 'lucide-react'

export const TOOL_LABELS = {
  web_search: 'Web search',
  calculator: 'Calculator',
  code_executor: 'Code exec',
  json_api_call: 'API calls',
  retrieve_context: 'Knowledge base',
}

export default function AgentCard({ agent, knowledgeBaseName, onEdit, onDelete }) {
  return (
    <div className="card flex flex-col p-5 transition-colors hover:border-brand-600/50">
      <div className="flex items-start gap-3">
        <div className="rounded-lg bg-brand-600/15 p-2 text-brand-400">
          <Bot className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="truncate font-semibold text-white">{agent.name}</h3>
          <p className="text-xs text-slate-500">
            {agent.model || 'default model'} · temp {agent.temperature}
          </p>
        </div>
      </div>

      <p className="mt-3 line-clamp-2 min-h-[2.5rem] text-sm text-slate-400">
        {agent.description || agent.system_prompt}
      </p>

      <div className="mt-4 flex flex-wrap gap-1.5">
        {agent.tools.map((tool) => (
          <span key={tool} className="badge bg-surface-overlay text-slate-300">
            {TOOL_LABELS[tool] || tool}
          </span>
        ))}
        {agent.knowledge_base_id && (
          <span className="badge bg-emerald-500/10 text-emerald-400">
            <BookOpen className="h-3 w-3" />
            {knowledgeBaseName || 'Knowledge base'}
          </span>
        )}
        {!agent.tools.length && !agent.knowledge_base_id && (
          <span className="badge bg-surface-overlay text-slate-500">No tools</span>
        )}
      </div>

      <div className="mt-5 flex items-center gap-2 border-t border-surface-border pt-4">
        <Link to={`/chat/${agent.id}`} className="btn-primary flex-1 py-1.5">
          <MessageSquare className="h-4 w-4" /> Chat
        </Link>
        <button onClick={() => onEdit(agent)} className="btn-secondary p-2" title="Edit" aria-label="Edit agent">
          <Pencil className="h-4 w-4" />
        </button>
        <button onClick={() => onDelete(agent)} className="btn-danger p-2" title="Delete" aria-label="Delete agent">
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
