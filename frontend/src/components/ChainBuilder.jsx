import { useState } from 'react'
import { ArrowDown, Bot, GitFork, GripVertical, Plus, Trash2 } from 'lucide-react'
import { getErrorMessage } from '../api/client'
import { ErrorBanner, Spinner } from './ui'

let keySeq = 0
const nextKey = () => `s${++keySeq}`

/**
 * UI model: an ordered list of { key, agent_id, parallel }. A step marked
 * `parallel` runs alongside the step before it. Consecutive parallel steps form a
 * "stage"; each stage depends on every step of the previous stage.
 */
export function stepsToApi(uiSteps) {
  const stages = []
  uiSteps.forEach((step, i) => {
    if (i > 0 && step.parallel) stages[stages.length - 1].push(step)
    else stages.push([step])
  })
  const apiSteps = []
  let previousIds = []
  let n = 0
  for (const stage of stages) {
    const ids = stage.map(() => `step_${++n}`)
    stage.forEach((step, j) => apiSteps.push({ id: ids[j], agent_id: step.agent_id, depends_on: previousIds }))
    previousIds = ids
  }
  return apiSteps
}

export function stepsFromApi(apiSteps = []) {
  const resolved = []
  apiSteps.forEach((s, i) => resolved.push(s.depends_on ?? (i > 0 ? [apiSteps[i - 1].id] : [])))
  const sameDeps = (a, b) => a.length === b.length && a.every((x) => b.includes(x))
  return apiSteps.map((s, i) => ({
    key: nextKey(),
    agent_id: s.agent_id,
    parallel: i > 0 && sameDeps(resolved[i], resolved[i - 1]),
  }))
}

/** Visual chain editor: drag agents from the palette into an ordered pipeline. */
export default function ChainBuilder({ agents, initial, onSave, onCancel }) {
  const [name, setName] = useState(initial?.name || '')
  const [description, setDescription] = useState(initial?.description || '')
  const [steps, setSteps] = useState(() => stepsFromApi(initial?.steps))
  const [dragIndex, setDragIndex] = useState(null)
  const [overIndex, setOverIndex] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const agentById = Object.fromEntries(agents.map((a) => [a.id, a]))

  const addAgent = (agentId, at = steps.length) =>
    setSteps((prev) => {
      const next = [...prev]
      next.splice(at, 0, { key: nextKey(), agent_id: agentId, parallel: false })
      return next
    })

  const moveStep = (from, to) =>
    setSteps((prev) => {
      const next = [...prev]
      const [item] = next.splice(from, 1)
      next.splice(to > from ? to - 1 : to, 0, item)
      return next
    })

  const onDropAt = (index) => (e) => {
    e.preventDefault()
    const agentId = e.dataTransfer.getData('application/x-agent-id')
    if (agentId) addAgent(agentId, index)
    else if (dragIndex !== null) moveStep(dragIndex, index)
    setDragIndex(null)
    setOverIndex(null)
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      await onSave({ name: name.trim(), description: description.trim(), steps: stepsToApi(steps) })
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to save chain'))
    } finally {
      setSaving(false)
    }
  }

  const renderDropZone = (index) => (
    <div
      key={`drop-${index}`}
      onDragOver={(e) => {
        e.preventDefault()
        setOverIndex(index)
      }}
      onDragLeave={() => setOverIndex(null)}
      onDrop={onDropAt(index)}
      className={`flex items-center justify-center transition-all ${overIndex === index ? 'h-10 rounded-lg border-2 border-dashed border-brand-500 bg-brand-600/10' : 'h-6'}`}
    >
      {overIndex !== index && index > 0 && index < steps.length && <ArrowDown className="h-3.5 w-3.5 text-slate-600" />}
    </div>
  )

  return (
    <div className="space-y-5">
      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="label" htmlFor="chain-name">Chain name</label>
          <input id="chain-name" className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Research → Write → Edit" />
        </div>
        <div>
          <label className="label" htmlFor="chain-desc">Description</label>
          <input id="chain-desc" className="input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional" />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
        <div>
          <p className="label">Agents</p>
          <div className="space-y-1.5">
            {agents.map((agent) => (
              <div
                key={agent.id}
                draggable
                onDragStart={(e) => e.dataTransfer.setData('application/x-agent-id', agent.id)}
                className="group flex cursor-grab items-center gap-2 rounded-lg border border-surface-border bg-surface-raised px-3 py-2 text-sm active:cursor-grabbing"
              >
                <Bot className="h-4 w-4 shrink-0 text-brand-400" />
                <span className="flex-1 truncate text-slate-200">{agent.name}</span>
                <button type="button" onClick={() => addAgent(agent.id)} className="text-slate-500 hover:text-brand-400" title="Add to chain" aria-label={`Add ${agent.name}`}>
                  <Plus className="h-4 w-4" />
                </button>
              </div>
            ))}
            {!agents.length && <p className="text-sm text-slate-500">Create agents first.</p>}
          </div>
        </div>

        <div className="rounded-xl border border-surface-border bg-surface p-4">
          <p className="label">Pipeline</p>
          {steps.length === 0 ? (
            <div
              onDragOver={(e) => {
                e.preventDefault()
                setOverIndex(0)
              }}
              onDragLeave={() => setOverIndex(null)}
              onDrop={onDropAt(0)}
              className={`flex h-32 items-center justify-center rounded-lg border-2 border-dashed text-sm ${
                overIndex === 0 ? 'border-brand-500 bg-brand-600/10 text-brand-400' : 'border-surface-border text-slate-500'
              }`}
            >
              Drag agents here to build the chain
            </div>
          ) : (
            <div>
              {renderDropZone(0)}
              {steps.map((step, index) => {
                const agent = agentById[step.agent_id]
                return (
                  <div key={step.key}>
                    <div
                      draggable
                      onDragStart={() => setDragIndex(index)}
                      onDragEnd={() => setDragIndex(null)}
                      className={`flex items-center gap-3 rounded-lg border bg-surface-raised px-3 py-2.5 ${
                        step.parallel ? 'ml-6 border-amber-500/40' : 'border-surface-border'
                      } ${dragIndex === index ? 'opacity-40' : ''}`}
                    >
                      <GripVertical className="h-4 w-4 cursor-grab text-slate-600" />
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-surface-overlay font-mono text-xs text-slate-400">{index + 1}</span>
                      <span className="flex-1 truncate text-sm text-slate-200">{agent?.name || 'Unknown agent'}</span>
                      {index > 0 && (
                        <label className="flex items-center gap-1.5 text-xs text-slate-400" title="Run in parallel with the previous step">
                          <input
                            type="checkbox"
                            className="accent-amber-500"
                            checked={step.parallel}
                            onChange={() => setSteps((prev) => prev.map((s, i) => (i === index ? { ...s, parallel: !s.parallel } : s)))}
                          />
                          <GitFork className="h-3.5 w-3.5" /> parallel
                        </label>
                      )}
                      <button
                        type="button"
                        onClick={() => setSteps((prev) => prev.filter((_, i) => i !== index))}
                        className="text-slate-500 hover:text-red-400"
                        aria-label="Remove step"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                    {renderDropZone(index + 1)}
                  </div>
                )
              })}
            </div>
          )}
          <p className="mt-2 text-xs text-slate-500">
            Each step receives the previous stage's output as its input. Mark steps <span className="text-amber-400">parallel</span> to run them concurrently on the same input.
          </p>
        </div>
      </div>

      <div className="flex justify-end gap-2 border-t border-surface-border pt-4">
        {onCancel && <button type="button" onClick={onCancel} className="btn-secondary">Cancel</button>}
        <button type="button" onClick={handleSave} disabled={saving || !name.trim() || !steps.length} className="btn-primary">
          {saving && <Spinner />}
          Save chain
        </button>
      </div>
    </div>
  )
}
