import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getErrorMessage } from '../api/client'
import { useAuth } from '../hooks/useAuth'
import { ErrorBanner, Spinner } from '../components/ui'
import { AuthShell } from './LoginPage'

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ fullName: '', email: '', password: '' })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (form.password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await register(form.email, form.password, form.fullName)
      navigate('/', { replace: true })
    } catch (err) {
      setError(getErrorMessage(err, 'Registration failed'))
      setSubmitting(false)
    }
  }

  return (
    <AuthShell
      title="Create your account"
      subtitle="Build agents, upload knowledge, chain them together"
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-brand-400 hover:text-brand-500">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <ErrorBanner message={error} />
        <div>
          <label className="label" htmlFor="name">Name</label>
          <input id="name" className="input" autoComplete="name" value={form.fullName} onChange={set('fullName')} placeholder="Optional" />
        </div>
        <div>
          <label className="label" htmlFor="email">Email</label>
          <input id="email" type="email" autoComplete="email" className="input" value={form.email} onChange={set('email')} required />
        </div>
        <div>
          <label className="label" htmlFor="password">Password</label>
          <input id="password" type="password" autoComplete="new-password" className="input" value={form.password} onChange={set('password')} minLength={8} maxLength={72} required />
          <p className="mt-1 text-xs text-slate-500">At least 8 characters</p>
        </div>
        <button type="submit" disabled={submitting} className="btn-primary w-full">
          {submitting && <Spinner />} Create account
        </button>
      </form>
    </AuthShell>
  )
}
