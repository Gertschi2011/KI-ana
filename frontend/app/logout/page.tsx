'use client'
import { useEffect } from 'react'
import { logout } from '../../lib/api'

export default function LogoutPage(){
  useEffect(()=>{
    (async()=>{
      try{ await logout() }catch{}
      try{ localStorage.clear() }catch{}
      window.location.replace('/login')
    })()
  },[])
  return <div className="card">Melde ab…</div>
}
