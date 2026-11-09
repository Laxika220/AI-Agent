import { useState } from 'react'
import { BookOpen, Calculator, ChevronRight, Code2, FileText, Globe, Plug, Wrench } from 'lucide-react'
import { Spinner } from './ui'

const TOOL_ICONS = {
  web_search: Globe,
  calculator: Calculator,
  code_executor: Code2,
  json_api_call: Plug,
  retrieve_context: BookOpen,
}

function JsonBlock({ value }) {
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  return (
    <pre className="scrollbar-thin max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-md bg-surface p-3 font-mono text-xs leading-relaxed text-slate-300">
      {text}
    </pre>
  )
}

/** Retrieved knowledge-base snippets, highlighted. */
export function RetrievedContext({ chunks }) {
  if (!chunks?.length) return null
  return (
    <div className="space-y-2">
      {chunks.map((chunk, i) => (
        <div key={`${chunk.doc_id}-${chunk.chunk_index}-${i}`} className="rounded-md border-l-2 border-emerald-500/70 bg-emerald-500/5 px-3 py-2">
          <div className="mb-1 flex items-center justify-between gap-2 text-[11px]">
            <span className="flex items-center gap-1 font-medium text-emerald-400">
              <FileText className="h-3 w-3" />
              {chunk.source_file} · chunk {chunk.chunk_index}
            </span>
            <span className="font-mono text-slate-500">score {Number(chunk.score).toFixed(3)}</span>
          </div>
          <p className="line-clamp-4 whitespace-pre-wrap text-xs leading-relaxed text-slate-300">{chunk.text}</p>
        </div>
      ))}
    </div>
  )
}

function ToolOutput({ call }) {
  if (call.error) return <p className="rounded-md bg-red-500/10 p-3 font-mono text-xs text-red-300">{call.error}</p>
  if (call.tool_name === 'retrieve_context' && Array.isArray(call.output)) {
    return call.output.length ? <RetrievedContext chunks={call.output} /> : <p className="text-xs text-slate-500">No relevant passages found.</p>
  }
  if (call.tool_name === 'code_executor' && call.output && typeof call.output === 'object') {
    return (
      <div className="space-y-2">
        {call.output.stdout && <JsonBlock value={call.output.stdout} />}
        {call.output.stderr && (
          <pre className="whitespace-pre-wrap rounded-md bg-red-500/5 p-3 font-mono text-xs text-red-300">{call.output.stderr}</pre>
        )}
        <p className="text-[11px] text-slate-500">exit code {String(call.output.exit_code)}</p>
      </div>
    )
  }
  return <JsonBlock value={call.output} />
}

/** Collapsible card: tool name → input → output. */
export default function ToolCallDisplay({ call }) {
  const [open, setOpen] = useState(false)
  const Icon = TOOL_ICONS[call.tool_name] || Wrench
  const running = call.status === 'running'

  return (
    <div className="overflow-hidden rounded-lg border border-surface-border bg-surface-overlay/60">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-surface-overlay"
        aria-expanded={open}
      >
        <ChevronRight className={`h-3.5 w-3.5 text-slate-500 transition-transform ${open ? 'rotate-90' : ''}`} />
        <Icon className="h-3.5 w-3.5 text-brand-400" />
        <span className="font-mono font-medium text-slate-200">{call.tool_name}</span>
        <span className="truncate font-mono text-slate-500">
          {call.input ? JSON.stringify(call.input).slice(0, 80) : ''}
        </span>
        <span className="ml-auto flex shrink-0 items-center gap-1.5">
          {running ? (
            <>
              <Spinner className="h-3 w-3 text-amber-400" /> <span className="text-amber-400">running</span>
            </>
          ) : call.error ? (
            <span className="text-red-400">failed</span>
          ) : (
            <span className="text-slate-500">{call.duration_ms != null ? `${Math.round(call.duration_ms)} ms` : 'done'}</span>
          )}
        </span>
      </button>
      {open && (
        <div className="space-y-3 border-t border-surface-border px-3 py-3">
          <div>
            <p className="label">Input</p>
            <JsonBlock value={call.input} />
          </div>
          {!running && (
            <div>
              <p className="label">Output</p>
              <ToolOutput call={call} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
