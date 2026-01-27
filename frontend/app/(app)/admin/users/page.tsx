'use client'
import { useEffect, useMemo, useState } from 'react'
import { getMe } from '../../../../lib/api'
import KianaCard from '../../../../components/ui/KianaCard'
import KianaButton from '../../../../components/ui/KianaButton'

type AdminUser = {
  id?: number | string
  username?: string
  email?: string
  role?: string
  roles?: any[]
  is_admin?: boolean
  is_creator?: boolean
  created_at?: string
  createdAt?: string
  status?: string
  suspended_reason?: string
  plan?: string
  plan_until?: number
  daily_quota?: number
  tier?: string
  locked_until?: number
  deleted_at?: number
  is_active?: boolean
}

type ApiOk<T> = { ok: true } & T
type ApiErr = { ok?: false; error?: string; detail?: string }

async function apiJson(url: string, opts: RequestInit = {}): Promise<{ res: Response; data: any }>{
  const res = await fetch(url, {
    credentials: 'include',
    headers: { 'content-type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  })
  const data = await res.json().catch(() => ({}))
  return { res, data }
}

function friendlyHttpError(res: Response, data: any): string {
  const detail = (data && (data.detail || data.error)) ? String(data.detail || data.error) : ''
  if (res.status === 401) return 'Bitte neu einloggen.'
  if (res.status === 403) return 'Kein Zugriff (nur Creator).'
  if (res.status === 404) return detail || 'Nicht gefunden.'
  if (res.status === 409) return 'Username oder E-Mail existiert bereits.'
  if (res.status === 429) return 'Zu viele Versuche. Bitte kurz warten und erneut versuchen.'
  return detail || `Request fehlgeschlagen (${res.status}).`
}

function asDateLabel(v: any): string {
  if (!v) return '–'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return String(v)
  return d.toLocaleString('de-DE')
}

export default function AdminUsersPage() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [users, setUsers] = useState<AdminUser[]>([])
  const [canManageUsers, setCanManageUsers] = useState<boolean>(false)

  const [toast, setToast] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [createOpen, setCreateOpen] = useState(false)
  const [editUser, setEditUser] = useState<AdminUser | null>(null)

  const [formUsername, setFormUsername] = useState('')
  const [formEmail, setFormEmail] = useState('')
  const [formPassword, setFormPassword] = useState('')
  const [formRole, setFormRole] = useState<'user' | 'user_pro'>('user')
  const [formStatus, setFormStatus] = useState<'active' | 'suspended' | 'banned' | 'deleted'>('active')
  const [formReason, setFormReason] = useState('')

  const columns = useMemo(
    () => [
      { key: 'id', label: 'ID' },
      { key: 'username', label: 'Benutzername' },
      { key: 'email', label: 'E-Mail' },
      { key: 'role', label: 'Rolle' },
      { key: 'created', label: 'Erstellt' },
      { key: 'flags', label: 'Flags' },
    ],
    [],
  )

  async function loadUsers() {
    setLoading(true)
    setError(null)
    setToast(null)
    try {
      const me: any = await getMe()
      const u: any = me?.auth ? me?.user : null
      const rolesRaw = Array.isArray(u?.roles) ? u.roles : []
      const role = String(u?.role || '').toLowerCase()
      const rolesLower = rolesRaw.map((r: any) => String(r).toLowerCase())
      const isCreator = !!u?.is_creator || rolesLower.includes('creator') || role === 'creator'
      const capsObj = (me?.caps && typeof me.caps === 'object') ? me.caps : ((u?.caps && typeof u.caps === 'object') ? u.caps : {})
      const can = Boolean(capsObj?.can_manage_users) || isCreator
      setCanManageUsers(can)
      if (!can) {
        setUsers([])
        return
      }

      const { res, data } = await apiJson('/api/admin/users')
      if (!res.ok || !data?.ok) {
        throw new Error(friendlyHttpError(res, data))
      }
      const list: any[] = Array.isArray(data?.items) ? data.items : []
      setUsers(list as AdminUser[])
    } catch {
      setUsers([])
      setError('Benutzerliste konnte nicht geladen werden. Bitte später erneut versuchen.')
    } finally {
      setLoading(false)
    }
  }

  function openCreate() {
    setToast(null)
    setError(null)
    setEditUser(null)
    setCreateOpen(true)
    setFormUsername('')
    setFormEmail('')
    setFormPassword('')
    setFormRole('user')
    setFormStatus('active')
    setFormReason('')
  }

  async function openEdit(u: AdminUser) {
    setToast(null)
    setError(null)
    setCreateOpen(false)
    setFormPassword('')
    setFormReason('')
    try {
      if (!u?.id) throw new Error('User-ID fehlt')
      const { res, data } = await apiJson(`/api/admin/users/${u.id}`)
      if (!res.ok || !data?.ok) throw new Error(friendlyHttpError(res, data))
      const detail: AdminUser = (data?.user && typeof data.user === 'object') ? data.user : u
      setEditUser(detail)
      setFormUsername(String(detail.username || ''))
      setFormEmail(String(detail.email || ''))
      setFormRole(((String(detail.role || 'user').toLowerCase() === 'user_pro') ? 'user_pro' : 'user') as any)
      const st = String(detail.status || 'active').toLowerCase()
      const stNorm = (st === 'active' || st === 'suspended' || st === 'banned' || st === 'deleted') ? st : 'active'
      setFormStatus(stNorm as any)
      setFormReason(String(detail.suspended_reason || ''))
    } catch (err: any) {
      setEditUser(u)
      setFormUsername(String(u.username || ''))
      setFormEmail(String(u.email || ''))
      setFormRole(((String(u.role || 'user').toLowerCase() === 'user_pro') ? 'user_pro' : 'user') as any)
      setFormStatus('active')
      setError(typeof err?.message === 'string' ? err.message : 'User konnte nicht geladen werden')
    }
  }

  async function submitCreate(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setToast(null)
    setError(null)
    try {
      const payload = {
        username: formUsername.trim(),
        email: formEmail.trim(),
        password: formPassword,
        role: formRole,
      }
      const created = await apiJson('/api/admin/users/create', { method: 'POST', body: JSON.stringify(payload) })
      if (!created.res.ok || !created.data?.ok) throw new Error(friendlyHttpError(created.res, created.data))
      const createdUser = (created.data?.user && typeof created.data.user === 'object') ? created.data.user : null
      const newId = createdUser?.id
      if (newId && formStatus !== 'active') {
        const stRes = await apiJson('/api/admin/users/set-status', {
          method: 'POST',
          body: JSON.stringify({ user_id: newId, status: formStatus, reason: formReason.trim() }),
        })
        if (!stRes.res.ok || !stRes.data?.ok) throw new Error(friendlyHttpError(stRes.res, stRes.data))
      }
      setToast('User angelegt.')
      setCreateOpen(false)
      await loadUsers()
    } catch (err: any) {
      setError(typeof err?.message === 'string' ? err.message : 'Anlegen fehlgeschlagen')
    } finally {
      setBusy(false)
    }
  }

  async function submitEdit(e: React.FormEvent) {
    e.preventDefault()
    if (!editUser?.id) return
    setBusy(true)
    setToast(null)
    setError(null)
    try {
      const uid = editUser.id
      const desiredRole = formRole
      const desiredStatus = formStatus

      const currentRole = String(editUser.role || '').toLowerCase()
      const currentStatus = String(editUser.status || '').toLowerCase() || 'active'

      if (desiredRole && desiredRole !== currentRole) {
        const { res, data } = await apiJson('/api/admin/users/set-role', {
          method: 'POST',
          body: JSON.stringify({ user_id: uid, role: desiredRole }),
        })
        if (!res.ok || !data?.ok) throw new Error(friendlyHttpError(res, data))
      }

      if (desiredStatus && desiredStatus !== currentStatus) {
        const { res, data } = await apiJson('/api/admin/users/set-status', {
          method: 'POST',
          body: JSON.stringify({ user_id: uid, status: desiredStatus, reason: formReason.trim() }),
        })
        if (!res.ok || !data?.ok) throw new Error(friendlyHttpError(res, data))
      }

      setToast('Änderungen gespeichert.')
      setEditUser(null)
      await loadUsers()
    } catch (err: any) {
      setError(typeof err?.message === 'string' ? err.message : 'Speichern fehlgeschlagen')
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    loadUsers()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (!canManageUsers && !loading) {
    return (
      <div className="max-w-5xl mx-auto grid gap-4">
        <KianaCard>
          <div className="text-lg font-semibold">Benutzerverwaltung</div>
          <div className="small mt-1">Kein Zugriff. Dieser Bereich ist nur für Creator/Admin sichtbar.</div>
          <div className="mt-4">
            <a href="/app/chat">
              <KianaButton variant="primary">Zurück zum Chat</KianaButton>
            </a>
          </div>
        </KianaCard>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto grid gap-4">
      <KianaCard>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="text-lg font-semibold">Benutzerverwaltung</div>
            <div className="small mt-1">Übersicht der registrierten Accounts.</div>
          </div>
          <div className="flex gap-2 flex-wrap">
            <KianaButton variant="ghost" onClick={loadUsers} disabled={loading}>
              Aktualisieren
            </KianaButton>
            <KianaButton variant="primary" onClick={openCreate} disabled={loading}>
              User anlegen
            </KianaButton>
          </div>
        </div>

        {toast ? <div className="mt-3 kiana-alert"><div className="small">{toast}</div></div> : null}

        {error ? (
          <div className="kiana-inset mt-4" role="status">
            <div className="font-semibold">Kurz notiert</div>
            <div className="small mt-1">{error}</div>
          </div>
        ) : null}

        <div className="mt-4 overflow-x-auto">
          <table className="kiana-table">
            <thead>
              <tr>
                {columns.map((c) => (
                  <th key={c.key}>{c.label}</th>
                ))}
                <th>Aktionen</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={columns.length} className="small">
                    Lade Benutzer…
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={columns.length} className="small">
                    Noch keine Einträge sichtbar. Sobald sich neue Accounts registrieren, erscheinen sie hier.
                  </td>
                </tr>
              ) : (
                users.map((u, idx) => {
                  const roles = Array.isArray(u.roles) ? u.roles.map((r) => String(r)).join(', ') : ''
                  const flags = [u.is_admin ? 'admin' : null, u.is_creator ? 'creator' : null].filter(Boolean).join(', ')
                  const created = u.created_at || u.createdAt
                  return (
                    <tr key={String(u.id ?? idx)}>
                      <td>{u.id ?? '–'}</td>
                      <td className="font-medium">{u.username || '–'}</td>
                      <td>{u.email || '–'}</td>
                      <td>{u.role || roles || '–'}</td>
                      <td>{asDateLabel(created)}</td>
                      <td>{flags || '–'}</td>
                      <td>
                        <KianaButton variant="ghost" onClick={() => openEdit(u)}>
                          Bearbeiten
                        </KianaButton>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </KianaCard>

      {createOpen ? (
        <KianaCard>
          <div className="text-lg font-semibold">User anlegen</div>
          <div className="small mt-1">Name, Rolle und Status festlegen.</div>
          <form className="form mt-4" onSubmit={submitCreate}>
            <label>
              <div className="small">Benutzername</div>
              <input className="input" value={formUsername} onChange={(e) => setFormUsername(e.target.value)} required />
            </label>
            <label>
              <div className="small">E-Mail</div>
              <input className="input" value={formEmail} onChange={(e) => setFormEmail(e.target.value)} required />
            </label>
            <label>
              <div className="small">Passwort</div>
              <input className="input" type="password" value={formPassword} onChange={(e) => setFormPassword(e.target.value)} required />
            </label>
            <label>
              <div className="small">Rolle</div>
              <select className="input" value={formRole} onChange={(e) => setFormRole(e.target.value as any)}>
                <option value="user">user</option>
                <option value="user_pro">user_pro</option>
              </select>
            </label>
            <label>
              <div className="small">Status</div>
              <select className="input" value={formStatus} onChange={(e) => setFormStatus(e.target.value as any)}>
                <option value="active">active</option>
                <option value="suspended">suspended</option>
                <option value="banned">banned</option>
                <option value="deleted">deleted</option>
              </select>
            </label>
            {formStatus !== 'active' ? (
              <label>
                <div className="small">Grund (optional)</div>
                <input className="input" value={formReason} onChange={(e) => setFormReason(e.target.value)} placeholder="z.B. Spam, Testaccount…" />
              </label>
            ) : null}
            <div className="flex gap-2 flex-wrap">
              <KianaButton variant="primary" type="submit" disabled={busy}>
                {busy ? 'Anlegen …' : 'Anlegen'}
              </KianaButton>
              <KianaButton variant="ghost" type="button" disabled={busy} onClick={() => setCreateOpen(false)}>
                Abbrechen
              </KianaButton>
            </div>
          </form>
        </KianaCard>
      ) : null}

      {editUser ? (
        <KianaCard>
          <div className="text-lg font-semibold">User bearbeiten</div>
          <div className="small mt-1">ID: {String(editUser.id)}</div>
          <form className="form mt-4" onSubmit={submitEdit}>
            <label>
              <div className="small">Benutzername</div>
              <input className="input" value={formUsername} disabled />
            </label>
            <label>
              <div className="small">E-Mail</div>
              <input className="input" value={formEmail} disabled />
            </label>
            <label>
              <div className="small">Rolle</div>
              <select className="input" value={formRole} onChange={(e) => setFormRole(e.target.value as any)}>
                <option value="user">user</option>
                <option value="user_pro">user_pro</option>
              </select>
            </label>
            <label>
              <div className="small">Status</div>
              <select className="input" value={formStatus} onChange={(e) => setFormStatus(e.target.value as any)}>
                <option value="active">active</option>
                <option value="suspended">suspended</option>
                <option value="banned">banned</option>
                <option value="deleted">deleted</option>
              </select>
            </label>
            {formStatus !== 'active' ? (
              <label>
                <div className="small">Grund (optional)</div>
                <input className="input" value={formReason} onChange={(e) => setFormReason(e.target.value)} placeholder="z.B. Spam, Testaccount…" />
              </label>
            ) : null}
            <div className="flex gap-2 flex-wrap">
              <KianaButton variant="primary" type="submit" disabled={busy}>
                {busy ? 'Speichern …' : 'Speichern'}
              </KianaButton>
              <KianaButton variant="ghost" type="button" disabled={busy} onClick={() => setEditUser(null)}>
                Abbrechen
              </KianaButton>
            </div>
          </form>
        </KianaCard>
      ) : null}
    </div>
  )
}
