import { useCallback, useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ChevronRight, Pencil, Play, Plus, Trash2, Workflow } from 'lucide-react'
import api, { getErrorMessage } from '../api/client'
import { useAgents } from '../hooks/useAgents'
import ChainBuilder from '../components/ChainBuilder'
import ToolCallDisplay from '../components/ToolCallDisplay'
import { EmptyState, ErrorBanner, PageHeader, Spinner, StatusBadge } from '../components/ui'

function StepTraceRow({ step, maxDuration }) {
  const [open, setOpen] = useState(false)
  const width = maxDuration ? Math.max((step.duration_ms / maxDuration) * 100, 2) : 0
  return (
    <div className="rounded-lg border border-surface-border bg-surface-raised">
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-3 px-4 py-3 text-left">
        <ChevronRight className={`h-4 w-4 text-slate-500 transition-transform ${open ? 'rotate-90' : ''}`} />
        <span className="font-mono text-xs text-slate-500">L{step.level}</span>
        <span className="flex-1 truncate text-sm font-medium text-slate-200">
          {step.agent_name} <span className="font-mono text-xs text-slate-500">({step.step_id})</span>
        </span>
        <div className="hidden w-40 sm:block">
          <div className="h-1.5 overflow-hidden rounded-full bg-surface-overlay">
            <div className="h-full rounded-full bg-brand-500" style={{ width: `${width}%` }} />
          </div>
        </div>
        <span className="w-16 text-right font-mono text-xs text-slate-400">{(step.duration_ms / 1000).toFixed(2)}s</span>
        <StatusBadge status={step.status} />
      </button>
      {open && (
        <div className="space-y-3 border-t border-surface-border px-4 py-3">
          <div>
            <p className="label">Input</p>
            <p className="max-h-40 overflow-auto whitespace-pre-wrap rounded-md bg-surface p-3 text-xs text-slate-400">{step.input || '—'}</p>
          </div>
          {step.tool_calls.length > 0 && (
            <div className="space-y-1.5">
              <p className="label">Tool calls</p>
              {step.tool_calls.map((call, i) => (
                <ToolCallDisplay key={i} call={{ ...call, status: 'done' }} />
              ))}
            </div>
          )}
          <div>
            <p className="label">Output</p>
            {step.error ? (
              <p className="rounded-md bg-red-500/10 p-3 text-xs text-red-300">{step.error}</p>
            ) : (
              <div className="prose prose-sm prose-invert max-w-none rounded-md bg-surface p-3">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{step.output || ''}</ReactMarkdown>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function ChainTrace({ run }) {
  const maxDuration = Math.max(...run.steps.map((s) => s.duration_ms), 1)
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-sm font-semibold text-white">Execution trace</h3>
        <StatusBadge status={run.status} />
        <span className="font-mono text-xs text-slate-500">total {(run.total_duration_ms / 1000).toFixed(2)}s</span>
      </div>
      <div className="space-y-2">
        {run.steps.map((step) => (
          <StepTraceRow key={step.step_id} step={step} maxDuration={maxDuration} />
        ))}
      </div>
      <div>
        <p className="label">Final output</p>
        <div className="prose prose-sm prose-invert max-w-none rounded-xl border border-brand-600/30 bg-brand-600/5 p-4">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{run.final_output || '_No output_'}</ReactMarkdown>
        </div>
      </div>
    </div>
  )
}

export default function ChainsPage() {
  const { agents } = useAgents()
  const [chains, setChains] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [mode, setMode] = useState('view') // 'view' | 'edit' | 'new'
  const [input, setInput] = useState('')
  const [running, setRunning] = useState(false)
  const [run, setRun] = useState(null)
  const [error, setError] = useState(null)

  const loadChains = useCallback(async () => {
    try {
      const { data } = await api.get('/chains')
      setChains(data)
      setSelectedId((current) => current ?? data[0]?.id ?? null)
      if (!data.length) setMode('new')
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to load chains'))
    }
  }, [])

  useEffect(() => {
    loadChains()
  }, [loadChains])

  // Show the latest run when switching chains.
  useEffect(() => {
    setRun(null)
    if (!selectedId) return
    api
      .get(`/chains/${selectedId}/runs`, { params: { limit: 1 } })
      .then(({ data }) => setRun(data[0] || null))
      .catch(() => {})
  }, [selectedId])

  const selected = chains.find((c) => c.id === selectedId)
  const agentName = (id) => agents.find((a) => a.id === id)?.name || 'Unknown'

  const save = async (payload) => {
    if (mode === 'edit' && selected) {
      const { data } = await api.put(`/chains/${selected.id}`, payload)
      setChains((prev) => prev.map((c) => (c.id === data.id ? data : c)))
    } else {
      const { data } = await api.post('/chains', payload)
      setChains((prev) => [data, ...prev])
      setSelectedId(data.id)
    }
    setMode('view')
  }

  const remove = async (chain) => {
    if (!window.confirm(`Delete chain "${chain.name}"?`)) return
    try {
      await api.delete(`/chains/${chain.id}`)
      setSelectedId(null)
      loadChains()
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to delete chain'))
    }
  }

  const execute = async (e) => {
    e.preventDefault()
    if (!selected || !input.trim()) return
    setRunning(true)
    setError(null)
    setRun(null)
    try {
      const { data } = await api.post(`/chains/${selected.id}/run`, { input })
      setRun(data)
    } catch (err) {
      setError(getErrorMessage(err, 'Chain execution failed'))
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-8">
      <PageHeader
        title="Chains"
        description="Orchestrate agents: each stage's output becomes the next stage's input."
        actions={
          <button onClick={() => setMode('new')} className="btn-primary">
            <Plus className="h-4 w-4" /> New chain
          </button>
        }
      />
      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
        <ul className="space-y-1">
          {chains.map((chain) => (
            <li key={chain.id}>
              <button
                onClick={() => {
                  setSelectedId(chain.id)
                  setMode('view')
                }}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left ${
                  chain.id === selectedId && mode !== 'new' ? 'bg-brand-600/15 text-brand-400' : 'text-slate-300 hover:bg-surface-overlay'
                }`}
              >
                <Workflow className="h-4 w-4 shrink-0" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{chain.name}</span>
                  <span className="text-xs text-slate-500">{chain.steps.length} steps</span>
                </span>
              </button>
            </li>
          ))}
          {!chains.length && <li className="px-3 text-sm text-slate-500">No chains yet</li>}
        </ul>

        <section className="min-w-0">
          {mode === 'new' || (mode === 'edit' && selected) ? (
            <div className="card p-5">
              <h2 className="mb-4 font-semibold text-white">{mode === 'new' ? 'New chain' : `Edit ${selected.name}`}</h2>
              <ChainBuilder
                key={mode === 'new' ? 'new' : selected.id}
                agents={agents}
                initial={mode === 'edit' ? selected : null}
                onSave={save}
                onCancel={chains.length ? () => setMode('view') : undefined}
              />
            </div>
          ) : !selected ? (
            <EmptyState icon={Workflow} title="No chain selected" description="Create a chain to orchestrate multiple agents." />
          ) : (
            <div className="space-y-6">
              <div className="card p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold text-white">{selected.name}</h2>
                    {selected.description && <p className="text-sm text-slate-400">{selected.description}</p>}
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => setMode('edit')} className="btn-secondary">
                      <Pencil className="h-4 w-4" /> Edit
                    </button>
                    <button onClick={() => remove(selected)} className="btn-danger" aria-label="Delete chain">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-2">
                  {selected.steps.map((step, i) => (
                    <span key={step.id} className="flex items-center gap-2">
                      {i > 0 && <ChevronRight className="h-4 w-4 text-slate-600" />}
                      <span className="badge bg-surface-overlay text-slate-300">
                        {agentName(step.agent_id)}
                        {step.depends_on && step.depends_on.length > 1 && <span className="text-amber-400">⇢ merge</span>}
                      </span>
                    </span>
                  ))}
                </div>

                <form onSubmit={execute} className="mt-5 space-y-3">
                  <label className="label" htmlFor="chain-input">Input</label>
                  <textarea
                    id="chain-input"
                    className="input min-h-[90px]"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="e.g. Research the latest trends in vector databases and write a short blog post"
                  />
                  <button type="submit" disabled={running || !input.trim()} className="btn-primary">
                    {running ? <Spinner /> : <Play className="h-4 w-4" />}
                    {running ? 'Running chain…' : 'Run chain'}
                  </button>
                </form>
              </div>

              {running && (
                <div className="card flex items-center gap-3 p-5 text-sm text-slate-400">
                  <Spinner /> Executing {selected.steps.length} steps…
                </div>
              )}
              {run && <ChainTrace run={run} />}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
