import { useEffect, useState } from 'react'
import api, { getErrorMessage } from '../api/client'
import { ErrorBanner, Spinner } from './ui'
import { TOOL_LABELS } from './AgentCard'

const DEFAULT_AGENT = {
  name: '',
  description: '',
  system_prompt: 'You are a helpful assistant. Think step by step and use tools when they help.',
  model: '',
  temperature: 0.7,
  tools: [],
  knowledge_base_id: '',
}

/** Create / edit form for an agent. Loads tools, models and knowledge bases itself. */
export default function AgentBuilder({ initial, onSubmit, onCancel }) {
  const [form, setForm] = useState(() => ({
    ...DEFAULT_AGENT,
    ...(initial || {}),
    model: initial?.model || '',
    knowledge_base_id: initial?.knowledge_base_id || '',
  }))
  const [tools, setTools] = useState([])
  const [models, setModels] = useState({ default: '', available: [] })
  const [knowledgeBases, setKnowledgeBases] = useState([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([api.get('/tools'), api.get('/models'), api.get('/knowledge-bases')])
      .then(([t, m, kb]) => {
        setTools(t.data)
        setModels(m.data)
        setKnowledgeBases(kb.data)
      })
      .catch((err) => setError(getErrorMessage(err, 'Failed to load options')))
  }, [])

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const toggleTool = (name) =>
    setForm((f) => ({
      ...f,
      tools: f.tools.includes(name) ? f.tools.filter((t) => t !== name) : [...f.tools, name],
    }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await onSubmit({
        name: form.name.trim(),
        description: form.description.trim(),
        system_prompt: form.system_prompt,
        model: form.model || null,
        temperature: Number(form.temperature),
        tools: form.tools,
        knowledge_base_id: form.knowledge_base_id || null,
      })
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to save agent'))
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="label" htmlFor="agent-name">Name</label>
          <input id="agent-name" className="input" value={form.name} onChange={set('name')} placeholder="Research Assistant" required maxLength={100} />
        </div>
        <div>
          <label className="label" htmlFor="agent-model">Model</label>
          <select id="agent-model" className="input" value={form.model} onChange={set('model')}>
            <option value="">Default ({models.default || '…'})</option>
            {models.available.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label className="label" htmlFor="agent-description">Description</label>
        <input id="agent-description" className="input" value={form.description} onChange={set('description')} placeholder="What does this agent do?" maxLength={500} />
      </div>

      <div>
        <label className="label" htmlFor="agent-prompt">System prompt</label>
        <textarea id="agent-prompt" className="input min-h-[140px] font-mono text-[13px] leading-relaxed" value={form.system_prompt} onChange={set('system_prompt')} required />
      </div>

      <div>
        <div className="flex items-center justify-between">
          <label className="label" htmlFor="agent-temp">Temperature</label>
          <span className="font-mono text-xs text-brand-400">{Number(form.temperature).toFixed(1)}</span>
        </div>
        <input id="agent-temp" type="range" min="0" max="2" step="0.1" value={form.temperature} onChange={set('temperature')} className="w-full accent-brand-500" />
        <div className="flex justify-between text-[11px] text-slate-500">
          <span>Precise</span>
          <span>Creative</span>
        </div>
      </div>

      <fieldset>
        <legend className="label">Tools</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {tools.map((tool) => (
            <label
              key={tool.name}
              className={`flex cursor-pointer gap-3 rounded-lg border p-3 transition-colors ${
                form.tools.includes(tool.name)
                  ? 'border-brand-500/60 bg-brand-600/10'
                  : 'border-surface-border hover:border-slate-600'
              }`}
            >
              <input type="checkbox" className="mt-0.5 accent-brand-500" checked={form.tools.includes(tool.name)} onChange={() => toggleTool(tool.name)} />
              <span>
                <span className="block text-sm font-medium text-slate-200">{TOOL_LABELS[tool.name] || tool.name}</span>
                <span className="line-clamp-2 text-xs text-slate-500">{tool.description}</span>
              </span>
            </label>
          ))}
          {!tools.length && <p className="text-sm text-slate-500">Loading tools…</p>}
        </div>
      </fieldset>

      <div>
        <label className="label" htmlFor="agent-kb">Knowledge base</label>
        <select id="agent-kb" className="input" value={form.knowledge_base_id} onChange={set('knowledge_base_id')}>
          <option value="">None</option>
          {knowledgeBases.map((kb) => (
            <option key={kb.id} value={kb.id}>
              {kb.name} ({kb.document_count} docs)
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-slate-500">Adds a retrieve_context tool that searches this knowledge base.</p>
      </div>

      <div className="flex justify-end gap-2 border-t border-surface-border pt-4">
        <button type="button" onClick={onCancel} className="btn-secondary">Cancel</button>
        <button type="submit" disabled={saving || !form.name.trim()} className="btn-primary">
          {saving && <Spinner />}
          {initial ? 'Save changes' : 'Create agent'}
        </button>
      </div>
    </form>
  )
}
