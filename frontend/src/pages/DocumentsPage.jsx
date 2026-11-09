import { useCallback, useEffect, useState } from 'react'
import { BookOpen, FileText, Plus, Trash2 } from 'lucide-react'
import api, { getErrorMessage } from '../api/client'
import DocumentUploader from '../components/DocumentUploader'
import { EmptyState, ErrorBanner, PageHeader, StatusBadge, formatBytes, formatRelative } from '../components/ui'

const POLL_MS = 2500

export default function DocumentsPage() {
  const [kbs, setKbs] = useState([])
  const [selectedKb, setSelectedKb] = useState(null)
  const [documents, setDocuments] = useState([])
  const [newKb, setNewKb] = useState({ name: '', description: '' })
  const [error, setError] = useState(null)

  const loadKbs = useCallback(async () => {
    try {
      const { data } = await api.get('/knowledge-bases')
      setKbs(data)
      setSelectedKb((current) => (current && data.some((kb) => kb.id === current) ? current : data[0]?.id || null))
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to load knowledge bases'))
    }
  }, [])

  const loadDocuments = useCallback(async () => {
    if (!selectedKb) {
      setDocuments([])
      return
    }
    try {
      const { data } = await api.get('/documents', { params: { knowledge_base_id: selectedKb } })
      setDocuments(data)
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to load documents'))
    }
  }, [selectedKb])

  useEffect(() => {
    loadKbs()
  }, [loadKbs])

  useEffect(() => {
    loadDocuments()
  }, [loadDocuments])

  // Poll while any document is still being processed.
  const busy = documents.some((d) => d.status === 'pending' || d.status === 'processing')
  useEffect(() => {
    if (!busy) return undefined
    const timer = setInterval(loadDocuments, POLL_MS)
    return () => clearInterval(timer)
  }, [busy, loadDocuments])

  const createKb = async (e) => {
    e.preventDefault()
    try {
      const { data } = await api.post('/knowledge-bases', newKb)
      setNewKb({ name: '', description: '' })
      setKbs((prev) => [data, ...prev])
      setSelectedKb(data.id)
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to create knowledge base'))
    }
  }

  const deleteKb = async (kb) => {
    if (!window.confirm(`Delete "${kb.name}" and all ${kb.document_count} documents? Agents using it will be detached.`)) return
    try {
      await api.delete(`/knowledge-bases/${kb.id}`)
      if (selectedKb === kb.id) setSelectedKb(null)
      loadKbs()
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to delete knowledge base'))
    }
  }

  const deleteDocument = async (doc) => {
    if (!window.confirm(`Delete "${doc.filename}"?`)) return
    try {
      await api.delete(`/documents/${doc.id}`)
      setDocuments((prev) => prev.filter((d) => d.id !== doc.id))
      loadKbs()
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to delete document'))
    }
  }

  const current = kbs.find((kb) => kb.id === selectedKb)

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-8">
      <PageHeader title="Documents" description="Knowledge bases power retrieval-augmented generation for your agents." />
      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <aside className="space-y-4">
          <form onSubmit={createKb} className="card space-y-3 p-4">
            <p className="label">New knowledge base</p>
            <input className="input" placeholder="Name" value={newKb.name} onChange={(e) => setNewKb((k) => ({ ...k, name: e.target.value }))} required maxLength={100} />
            <input className="input" placeholder="Description (optional)" value={newKb.description} onChange={(e) => setNewKb((k) => ({ ...k, description: e.target.value }))} maxLength={500} />
            <button type="submit" className="btn-primary w-full" disabled={!newKb.name.trim()}>
              <Plus className="h-4 w-4" /> Create
            </button>
          </form>

          <ul className="space-y-1">
            {kbs.map((kb) => (
              <li key={kb.id} className="group relative">
                <button
                  onClick={() => setSelectedKb(kb.id)}
                  className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 pr-9 text-left ${
                    kb.id === selectedKb ? 'bg-brand-600/15 text-brand-400' : 'text-slate-300 hover:bg-surface-overlay'
                  }`}
                >
                  <BookOpen className="h-4 w-4 shrink-0" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{kb.name}</span>
                    <span className="text-xs text-slate-500">{kb.document_count} documents</span>
                  </span>
                </button>
                <button onClick={() => deleteKb(kb)} className="absolute right-2 top-3 hidden text-slate-500 hover:text-red-400 group-hover:block" aria-label={`Delete ${kb.name}`}>
                  <Trash2 className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="min-w-0 space-y-6">
          {!current ? (
            <EmptyState icon={BookOpen} title="Create a knowledge base" description="Group related documents into a knowledge base, then attach it to an agent." />
          ) : (
            <>
              <div>
                <h2 className="text-lg font-semibold text-white">{current.name}</h2>
                {current.description && <p className="text-sm text-slate-400">{current.description}</p>}
              </div>

              <DocumentUploader knowledgeBaseId={current.id} onUploaded={(doc) => {
                setDocuments((prev) => [doc, ...prev])
                setKbs((prev) => prev.map((kb) => (kb.id === current.id ? { ...kb, document_count: kb.document_count + 1 } : kb)))
              }} />

              <div className="card overflow-hidden">
                {documents.length === 0 ? (
                  <p className="p-6 text-center text-sm text-slate-500">No documents in this knowledge base yet.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="border-b border-surface-border text-left text-xs uppercase tracking-wide text-slate-500">
                        <tr>
                          <th className="px-4 py-3 font-medium">File</th>
                          <th className="px-4 py-3 font-medium">Status</th>
                          <th className="px-4 py-3 font-medium">Chunks</th>
                          <th className="px-4 py-3 font-medium">Size</th>
                          <th className="px-4 py-3 font-medium">Added</th>
                          <th className="px-4 py-3" />
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-surface-border">
                        {documents.map((doc) => (
                          <tr key={doc.id} className="hover:bg-surface-overlay/40">
                            <td className="max-w-[260px] px-4 py-3">
                              <div className="flex items-center gap-2">
                                <FileText className="h-4 w-4 shrink-0 text-slate-500" />
                                <span className="truncate text-slate-200" title={doc.filename}>{doc.filename}</span>
                              </div>
                              {doc.error && <p className="mt-1 truncate text-xs text-red-400" title={doc.error}>{doc.error}</p>}
                            </td>
                            <td className="px-4 py-3"><StatusBadge status={doc.status} /></td>
                            <td className="px-4 py-3 font-mono text-slate-400">{doc.chunk_count || '—'}</td>
                            <td className="px-4 py-3 text-slate-400">{formatBytes(doc.size_bytes)}</td>
                            <td className="px-4 py-3 text-slate-500">{formatRelative(doc.created_at)}</td>
                            <td className="px-4 py-3 text-right">
                              <button onClick={() => deleteDocument(doc)} className="text-slate-500 hover:text-red-400" aria-label={`Delete ${doc.filename}`}>
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
