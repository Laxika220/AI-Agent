import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { getErrorMessage } from '../api/client'
import { useAuth } from '../hooks/useAuth'
import { ErrorBanner, Spinner } from '../components/ui'

export function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="flex min-h-full items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 font-bold text-white">
            AF
          </div>
          <h1 className="text-xl font-semibold text-white">{title}</h1>
          <p className="mt-1 text-sm text-slate-400">{subtitle}</p>
        </div>
        <div className="card p-6">{children}</div>
        <p className="mt-6 text-center text-sm text-slate-400">{footer}</p>
      </div>
    </div>
  )
}

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await login(email, password)
      navigate(location.state?.from || '/', { replace: true })
    } catch (err) {
      setError(getErrorMessage(err, 'Login failed'))
      setSubmitting(false)
    }
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to your AgentForge workspace"
      footer={
        <>
          No account?{' '}
          <Link to="/register" className="font-medium text-brand-400 hover:text-brand-500">
            Create one
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <ErrorBanner message={error} />
        <div>
          <label className="label" htmlFor="email">Email</label>
          <input id="email" type="email" autoComplete="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div>
          <label className="label" htmlFor="password">Password</label>
          <input id="password" type="password" autoComplete="current-password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        <button type="submit" disabled={submitting} className="btn-primary w-full">
          {submitting && <Spinner />} Sign in
        </button>
      </form>
    </AuthShell>
  )
}
