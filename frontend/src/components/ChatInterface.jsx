import { useCallback, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { AlertTriangle, ArrowUp, Bot, Square, User } from 'lucide-react'
import api, { getErrorMessage } from '../api/client'
import { useSSE } from '../hooks/useSSE'
import ToolCallDisplay from './ToolCallDisplay'
import { ErrorBanner, Spinner } from './ui'

const toUiMessage = (m) => ({
  id: m.id,
  role: m.role,
  content: m.content,
  toolCalls: (m.tool_calls || []).map((tc, i) => ({ ...tc, run_id: `${m.id}-${i}`, status: 'done' })),
})

function MessageBubble({ message }) {
  const isUser = message.role === 'user'
  const showCursor = message.streaming && !message.error

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          isUser ? 'bg-surface-overlay text-slate-300' : 'bg-brand-600/20 text-brand-400'
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      <div className={`min-w-0 max-w-[85%] space-y-2 ${isUser ? 'items-end text-right' : ''}`}>
        {message.toolCalls?.length > 0 && (
          <div className="space-y-1.5 text-left">
            {message.toolCalls.map((call) => (
              <ToolCallDisplay key={call.run_id} call={call} />
            ))}
          </div>
        )}

        {isUser ? (
          <div className="inline-block whitespace-pre-wrap rounded-2xl rounded-tr-sm bg-brand-600 px-4 py-2.5 text-left text-sm text-white">
            {message.content}
          </div>
        ) : (
          (message.content || showCursor) && (
            <div
              className={`prose prose-sm prose-invert max-w-none rounded-2xl rounded-tl-sm bg-surface-raised px-4 py-3 prose-pre:bg-surface prose-pre:text-xs ${
                showCursor ? 'cursor-blink' : ''
              }`}
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content || ''}</ReactMarkdown>
            </div>
          )
        )}

        {message.error && (
          <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-left text-sm text-red-300">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            {message.error}
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * Streaming chat with an agent. Shows tokens as they arrive, tool calls as
 * collapsible cards, and retrieved knowledge-base passages.
 */
export default function ChatInterface({ agent, conversationId, onConversationCreated }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [error, setError] = useState(null)
  const { start, abort, isStreaming } = useSSE()
  const bottomRef = useRef(null)
  const createdHereRef = useRef(null) // conversation we just created by streaming
  const textareaRef = useRef(null)

  // Load history when switching conversations (but not the one we just created).
  useEffect(() => {
    if (!conversationId) {
      setMessages([])
      return
    }
    if (conversationId === createdHereRef.current) return
    let cancelled = false
    setLoadingHistory(true)
    api
      .get(`/chat/conversations/${conversationId}`)
      .then(({ data }) => !cancelled && setMessages(data.messages.map(toUiMessage)))
      .catch((err) => !cancelled && setError(getErrorMessage(err, 'Failed to load conversation')))
      .finally(() => !cancelled && setLoadingHistory(false))
    return () => {
      cancelled = true
    }
  }, [conversationId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages])

  const updateAssistant = useCallback((updater) => {
    setMessages((prev) => {
      const next = [...prev]
      const last = next[next.length - 1]
      if (last?.role === 'assistant') next[next.length - 1] = updater(last)
      return next
    })
  }, [])

  const handleEvent = useCallback(
    (event, data) => {
      switch (event) {
        case 'conversation':
          if (!conversationId) {
            createdHereRef.current = data.conversation_id
            onConversationCreated?.(data.conversation_id)
          }
          break
        case 'token':
          updateAssistant((m) => ({ ...m, content: m.content + data.content }))
          break
        case 'tool_start':
          updateAssistant((m) => ({
            ...m,
            toolCalls: [...m.toolCalls, { run_id: data.run_id, tool_name: data.tool_name, input: data.input, status: 'running' }],
          }))
          break
        case 'tool_end':
          updateAssistant((m) => ({
            ...m,
            toolCalls: m.toolCalls.map((c) => (c.run_id === data.run_id ? { ...c, ...data, status: 'done' } : c)),
          }))
          break
        case 'done':
          updateAssistant((m) => ({ ...m, id: data.id, content: data.content || m.content, streaming: false }))
          break
        case 'error':
          updateAssistant((m) => ({ ...m, streaming: false, error: data.message }))
          break
        default:
          break // 'retrieval' is already shown inside the retrieve_context tool card
      }
    },
    [conversationId, onConversationCreated, updateAssistant],
  )

  const send = async (e) => {
    e?.preventDefault()
    const text = input.trim()
    if (!text || isStreaming || !agent) return
    setInput('')
    setError(null)
    setMessages((prev) => [
      ...prev,
      { id: `local-${Date.now()}`, role: 'user', content: text, toolCalls: [] },
      { id: `pending-${Date.now()}`, role: 'assistant', content: '', toolCalls: [], streaming: true },
    ])
    await start(`/chat/${agent.id}`, { message: text, conversation_id: conversationId || null }, handleEvent)
    updateAssistant((m) => (m.streaming ? { ...m, streaming: false } : m))
    textareaRef.current?.focus()
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="scrollbar-thin flex-1 overflow-y-auto px-4 py-6 sm:px-8">
        <div className="mx-auto max-w-3xl space-y-6">
          <ErrorBanner message={error} onDismiss={() => setError(null)} />
          {loadingHistory && (
            <div className="flex justify-center py-10 text-slate-500">
              <Spinner className="h-5 w-5" />
            </div>
          )}
          {!loadingHistory && messages.length === 0 && agent && (
            <div className="py-16 text-center">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600/15 text-brand-400">
                <Bot className="h-6 w-6" />
              </div>
              <h2 className="font-semibold text-white">Chat with {agent.name}</h2>
              <p className="mx-auto mt-1 max-w-md text-sm text-slate-400">{agent.description || 'Ask anything to get started.'}</p>
            </div>
          )}
          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      <form onSubmit={send} className="border-t border-surface-border bg-surface px-4 py-4 sm:px-8">
        <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-xl border border-surface-border bg-surface-raised p-2 focus-within:border-brand-500">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder={agent ? `Message ${agent.name}…` : 'Select an agent to start chatting'}
            disabled={!agent}
            className="max-h-40 min-h-[40px] flex-1 resize-none bg-transparent px-2 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none"
          />
          {isStreaming ? (
            <button type="button" onClick={abort} className="btn-secondary h-10 w-10 p-0" title="Stop" aria-label="Stop generating">
              <Square className="h-4 w-4" />
            </button>
          ) : (
            <button type="submit" disabled={!input.trim() || !agent} className="btn-primary h-10 w-10 p-0" aria-label="Send">
              <ArrowUp className="h-4 w-4" />
            </button>
          )}
        </div>
        <p className="mx-auto mt-2 max-w-3xl text-center text-[11px] text-slate-600">Enter to send · Shift+Enter for a new line</p>
      </form>
    </div>
  )
}
