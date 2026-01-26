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
  active?: boolean
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
    try {
      const me: any = await getMe()
      const u: any = me?.auth ? me?.user : null
      const rolesRaw = Array.isArray(u?.roles) ? u.roles : []
      const role = String(u?.role || '').toLowerCase()
      const rolesLower = rolesRaw.map((r: any) => String(r).toLowerCase())
      const isAdmin = !!u?.is_admin || rolesLower.includes('admin') || role === 'admin'
      const isCreator = !!u?.is_creator || rolesLower.includes('creator') || role === 'creator'
      const capsObj = (me?.caps && typeof me.caps === 'object') ? me.caps : ((u?.caps && typeof u.caps === 'object') ? u.caps : {})
      const can = Boolean(capsObj?.can_manage_users) || isAdmin || isCreator
      setCanManageUsers(can)
      if (!can) {
        setUsers([])
        return
      }

      const candidates = ['/api/admin/users', '/api/users', '/api/admin/user/list']
      let lastStatus: number | null = null
      let lastText: string | null = null
      for (const url of candidates) {
        const res = await fetch(url, { credentials: 'include' })
        if (res.ok) {
          const data: any = await res.json().catch(() => ({}))
          const list: any[] =
            (Array.isArray(data?.users) && data.users) ||
            (Array.isArray(data?.items) && data.items) ||
            (Array.isArray(data) && data) ||
            []
          setUsers(list as AdminUser[])
          return
        }
        lastStatus = res.status
        lastText = await res.text().catch(() => '')
      }
      setUsers([])
      setError(`Benutzerliste konnte nicht geladen werden (${lastStatus ?? 'unbekannt'}).` + (lastText ? ' Bitte später erneut versuchen.' : ''))
    } catch {
      setUsers([])
      setError('Benutzerliste konnte nicht geladen werden. Bitte später erneut versuchen.')
    } finally {
      setLoading(false)
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
          <KianaButton variant="primary" onClick={loadUsers} disabled={loading}>
            Aktualisieren
          </KianaButton>
        </div>

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
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </KianaCard>
    </div>
  )
}
