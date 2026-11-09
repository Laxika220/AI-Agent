import { useCallback, useEffect, useRef, useState } from 'react'
import { API_URL, refreshAccessToken, tokenStore } from '../api/client'

/**
 * Parse a text/event-stream body into { event, data } objects.
 * EventSource can't send POST bodies or auth headers, so we read the
 * fetch() stream ourselves.
 */
async function* parseSSE(body) {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let boundary
    while ((boundary = buffer.indexOf('\n\n')) !== -1) {
      const rawEvent = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      let event = 'message'
      const dataLines = []
      for (const line of rawEvent.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
      }
      if (!dataLines.length) continue
      const raw = dataLines.join('\n')
      let data
      try {
        data = JSON.parse(raw)
      } catch {
        data = raw
      }
      yield { event, data }
    }
  }
}

async function postStream(path, body, signal, retry = true) {
  const response = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      Authorization: `Bearer ${tokenStore.getAccess()}`,
    },
    body: JSON.stringify(body),
    signal,
  })
  if (response.status === 401 && retry) {
    await refreshAccessToken()
    return postStream(path, body, signal, false)
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const json = await response.json()
      message = json?.error?.message || message
    } catch {
      /* not JSON */
    }
    throw new Error(message)
  }
  return response
}

/**
 * Stream an SSE POST endpoint.
 *
 *   const { start, abort, isStreaming } = useSSE()
 *   await start('/chat/123', { message }, (event, data) => { ... })
 */
export function useSSE() {
  const controllerRef = useRef(null)
  const [isStreaming, setIsStreaming] = useState(false)

  const abort = useCallback(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
    setIsStreaming(false)
  }, [])

  useEffect(() => abort, [abort])

  const start = useCallback(async (path, body, onEvent) => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    setIsStreaming(true)
    try {
      const response = await postStream(path, body, controller.signal)
      for await (const { event, data } of parseSSE(response.body)) {
        onEvent(event, data)
      }
    } catch (error) {
      if (error.name !== 'AbortError') onEvent('error', { message: error.message })
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null
        setIsStreaming(false)
      }
    }
  }, [])

  return { start, abort, isStreaming }
}
