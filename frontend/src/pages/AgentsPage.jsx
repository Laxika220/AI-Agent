import { useEffect, useState } from 'react'
import { Bot, Plus } from 'lucide-react'
import api, { getErrorMessage } from '../api/client'
import { useAgents } from '../hooks/useAgents'
import AgentBuilder from '../components/AgentBuilder'
import AgentCard from '../components/AgentCard'
import { EmptyState, ErrorBanner, Modal, PageHeader, Spinner } from '../components/ui'

export default function AgentsPage() {
  const { agents, loading, error, createAgent, updateAgent, deleteAgent } = useAgents()
  const [editing, setEditing] = useState(null) // null = closed, {} = new, agent = edit
  const [kbNames, setKbNames] = useState({})
  const [actionError, setActionError] = useState(null)

  useEffect(() => {
    api
      .get('/knowledge-bases')
      .then(({ data }) => setKbNames(Object.fromEntries(data.map((kb) => [kb.id, kb.name]))))
      .catch(() => {})
  }, [])

  const handleSubmit = async (payload) => {
    if (editing?.id) await updateAgent(editing.id, payload)
    else await createAgent(payload)
    setEditing(null)
  }

  const handleDelete = async (agent) => {
    if (!window.confirm(`Delete "${agent.name}" and all its conversations?`)) return
    try {
      await deleteAgent(agent.id)
    } catch (err) {
      setActionError(getErrorMessage(err, 'Failed to delete agent'))
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-8">
      <PageHeader
        title="Agents"
        description="Configure system prompts, models, tools and knowledge bases."
        actions={
          <button onClick={() => setEditing({})} className="btn-primary">
            <Plus className="h-4 w-4" /> New agent
          </button>
        }
      />
      <ErrorBanner message={error || actionError} onDismiss={() => setActionError(null)} />

      {loading ? (
        <div className="flex justify-center py-20 text-slate-500">
          <Spinner className="h-6 w-6" />
        </div>
      ) : agents.length === 0 ? (
        <EmptyState
          icon={Bot}
          title="No agents yet"
          description="Create your first agent: give it a personality, pick tools, and optionally attach a knowledge base."
          action={
            <button onClick={() => setEditing({})} className="btn-primary">
              <Plus className="h-4 w-4" /> Create agent
            </button>
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {agents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              knowledgeBaseName={kbNames[agent.knowledge_base_id]}
              onEdit={setEditing}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      <Modal open={editing !== null} title={editing?.id ? `Edit ${editing.name}` : 'New agent'} onClose={() => setEditing(null)} wide>
        {editing !== null && (
          <AgentBuilder initial={editing.id ? editing : null} onSubmit={handleSubmit} onCancel={() => setEditing(null)} />
        )}
      </Modal>
    </div>
  )
}
