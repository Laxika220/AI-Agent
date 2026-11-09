import { useRef, useState } from 'react'
import { CheckCircle2, UploadCloud, XCircle } from 'lucide-react'
import api, { getErrorMessage } from '../api/client'
import { formatBytes } from './ui'

const ACCEPTED = ['.pdf', '.txt', '.md', '.docx']

const extensionOf = (name) => name.slice(name.lastIndexOf('.')).toLowerCase()

/** Drag-and-drop uploader with per-file progress. */
export default function DocumentUploader({ knowledgeBaseId, onUploaded }) {
  const [dragging, setDragging] = useState(false)
  const [uploads, setUploads] = useState([])
  const inputRef = useRef(null)

  const patch = (key, changes) => setUploads((prev) => prev.map((u) => (u.key === key ? { ...u, ...changes } : u)))

  const uploadFile = async (file) => {
    const key = `${file.name}-${file.size}-${Date.now()}-${Math.random()}`
    setUploads((prev) => [{ key, name: file.name, size: file.size, progress: 0, state: 'uploading' }, ...prev])

    if (!ACCEPTED.includes(extensionOf(file.name))) {
      patch(key, { state: 'error', error: `Unsupported type. Use ${ACCEPTED.join(', ')}` })
      return
    }

    const body = new FormData()
    body.append('file', file)
    body.append('knowledge_base_id', knowledgeBaseId)
    try {
      const { data } = await api.post('/documents/upload', body, {
        onUploadProgress: (e) => e.total && patch(key, { progress: Math.round((e.loaded / e.total) * 100) }),
      })
      patch(key, { progress: 100, state: 'done' })
      onUploaded?.(data)
    } catch (err) {
      patch(key, { state: 'error', error: getErrorMessage(err, 'Upload failed') })
    }
  }

  const handleFiles = async (fileList) => {
    // Sequential uploads keep progress readable and avoid hammering the embedder.
    for (const file of Array.from(fileList)) {
      await uploadFile(file)
    }
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    if (e.dataTransfer.files?.length) handleFiles(e.dataTransfer.files)
  }

  return (
    <div className="space-y-3">
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${
          dragging ? 'border-brand-500 bg-brand-600/10' : 'border-surface-border hover:border-slate-600 hover:bg-surface-raised'
        }`}
      >
        <UploadCloud className={`mb-3 h-8 w-8 ${dragging ? 'text-brand-400' : 'text-slate-500'}`} />
        <p className="text-sm font-medium text-slate-200">Drop files here or click to browse</p>
        <p className="mt-1 text-xs text-slate-500">PDF, TXT, Markdown or DOCX — chunked, embedded and indexed automatically</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED.join(',')}
          className="hidden"
          onChange={(e) => {
            handleFiles(e.target.files)
            e.target.value = ''
          }}
        />
      </div>

      {uploads.length > 0 && (
        <ul className="space-y-2">
          {uploads.slice(0, 6).map((u) => (
            <li key={u.key} className="rounded-lg border border-surface-border bg-surface-raised px-3 py-2">
              <div className="flex items-center gap-2 text-sm">
                <span className="flex-1 truncate text-slate-200">{u.name}</span>
                <span className="text-xs text-slate-500">{formatBytes(u.size)}</span>
                {u.state === 'done' && <CheckCircle2 className="h-4 w-4 text-emerald-400" />}
                {u.state === 'error' && <XCircle className="h-4 w-4 text-red-400" />}
              </div>
              {u.state === 'uploading' && (
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-overlay">
                  <div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${u.progress}%` }} />
                </div>
              )}
              {u.state === 'error' && <p className="mt-1 text-xs text-red-400">{u.error}</p>}
              {u.state === 'done' && <p className="mt-1 text-xs text-slate-500">Uploaded — processing in background</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
