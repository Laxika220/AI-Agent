import { useCallback, useEffect, useState } from 'react'
import api, { getErrorMessage } from '../api/client'

/** Agent CRUD with local state kept in sync. */
export function useAgents() {
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/agents')
      setAgents(data)
      setError(null)
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to load agents'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const createAgent = useCallback(async (payload) => {
    const { data } = await api.post('/agents', payload)
    setAgents((prev) => [data, ...prev])
    return data
  }, [])

  const updateAgent = useCallback(async (id, payload) => {
    const { data } = await api.put(`/agents/${id}`, payload)
    setAgents((prev) => prev.map((a) => (a.id === id ? data : a)))
    return data
  }, [])

  const deleteAgent = useCallback(async (id) => {
    await api.delete(`/agents/${id}`)
    setAgents((prev) => prev.filter((a) => a.id !== id))
  }, [])

  return { agents, loading, error, refresh, createAgent, updateAgent, deleteAgent }
}
