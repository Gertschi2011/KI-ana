"use client";
import { useEffect, useMemo, useRef, useState } from 'react';

type Msg = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  createdAt?: number | string;
  sources?: any[];
  memory_ids?: string[];
  origin?: string;
  topic?: string;
  explain?: any;
};

export default function ChatPage() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const startingStreamRef = useRef(false);
  const finalizeSeenRef = useRef(false);
  const activeRequestIdRef = useRef<string | null>(null);
  const [canExplain, setCanExplain] = useState(false);
  const [showExplain, setShowExplain] = useState(true);
  const [webOkAllowed, setWebOkAllowed] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [folders, setFolders] = useState<any[]>([]);
  const [foldersAvailable, setFoldersAvailable] = useState(true);
  const [convs, setConvs] = useState<any[]>([]);
  const [activeFolderId, setActiveFolderId] = useState<number | null>(null);
  const [activeConvId, setActiveConvId] = useState<number | null>(null);
  const [movePickerConvId, setMovePickerConvId] = useState<number | null>(null);
  const [movePickerFolderId, setMovePickerFolderId] = useState<number | null>(null);
  const [activeConvFolderPick, setActiveConvFolderPick] = useState<number | null>(null);
  const [explainOpenMsgId, setExplainOpenMsgId] = useState<string | null>(null);
  const scrollerRef = useRef<HTMLDivElement>(null);
  const convRef = useRef<string | null>(null);
  const bufferRef = useRef<string>("");
  const assistantIdRef = useRef<string | null>(null);
  const activeControllerRef = useRef<AbortController | null>(null);

  const uiBusy = busy || startingStreamRef.current;

  const canShowExplainUi = useMemo(() => {
    return !!(showExplain && canExplain);
  }, [showExplain, canExplain]);

  const explainOpenMsg = explainOpenMsgId
    ? msgs.find((m) => m.id === explainOpenMsgId) || null
    : null;

  useEffect(() => {
    scrollerRef.current?.scrollTo({ top: scrollerRef.current.scrollHeight });
  }, [msgs.length, busy]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const r = await fetch('/api/me', { credentials: 'include' });
        const j = await r.json().catch(() => ({} as any));
        const u = j?.auth ? j.user : null;
        const role = String(u?.role ?? '').toLowerCase();
        const roles = Array.isArray(u?.roles) ? u.roles.map((x: any) => String(x).toLowerCase()) : [];
        const isAdmin = !!u?.is_admin || roles.includes('admin') || role === 'admin';
        const isCreator = !!u?.is_creator || roles.includes('creator') || role === 'creator';
        if (mounted) setCanExplain(!!(isAdmin || isCreator));
      } catch {
        if (mounted) setCanExplain(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    try {
      const v = localStorage.getItem('kiana_show_explain');
      if (v === '0') setShowExplain(false);
    } catch {}
  }, []);

  useEffect(() => {
    try {
      const v = localStorage.getItem('kiana_web_ok');
      setWebOkAllowed(v === '1');
    } catch {
      setWebOkAllowed(false);
    }
  }, []);

  async function refreshFolders() {
    try {
      const r = await fetch('/api/folders', { credentials: 'include' });
      if (!r.ok) {
        setFoldersAvailable(false);
        setFolders([]);
        return;
      }
      const j = await r.json().catch(() => ({} as any));
      setFoldersAvailable(true);
      setFolders(Array.isArray(j?.folders) ? j.folders : []);
    } catch {
      setFoldersAvailable(false);
      setFolders([]);
    }
  }

  async function refreshConversations() {
    try {
      const r = await fetch('/api/chat/conversations', { credentials: 'include' });
      const j = await r.json().catch(() => ({} as any));
      const items = Array.isArray(j?.items) ? j.items : [];
      setConvs(items);
    } catch {
      setConvs([]);
    }
  }

  async function createFolder() {
    if (!foldersAvailable) return;
    const name = prompt('Ordnername');
    if (!name) return;
    try {
      await fetch('/api/folders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ name: name.trim(), icon: '📁' }),
      });
      await refreshFolders();
    } catch {}
  }

  async function renameFolder(folderId: number) {
    if (!foldersAvailable) return;
    const cur = folders.find((f: any) => Number(f?.id) === Number(folderId));
    const name = prompt('Neuer Ordnername', String(cur?.name ?? ''));
    if (!name) return;
    try {
      await fetch(`/api/folders/${folderId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ name: name.trim() }),
      });
      await refreshFolders();
    } catch {}
  }

  async function deleteFolder(folderId: number) {
    if (!foldersAvailable) return;
    if (!confirm('Ordner wirklich löschen? (Unterhaltungen bleiben erhalten)')) return;
    try {
      await fetch(`/api/folders/${folderId}`, { method: 'DELETE', credentials: 'include' });
      if (Number(activeFolderId) === Number(folderId)) setActiveFolderId(null);
      await refreshFolders();
      await refreshConversations();
    } catch {}
  }

  async function moveActiveConversationToFolder(folderId: number) {
    if (!foldersAvailable) return;
    if (!activeConvId) return;
    try {
      await fetch(`/api/folders/${folderId}/conversations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ conversation_ids: [Number(activeConvId)] }),
      });
      await refreshFolders();
      await refreshConversations();
      setActiveFolderId(folderId);
    } catch {}
  }

  useEffect(() => {
    refreshFolders();
    refreshConversations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredConvs = activeFolderId == null ? convs : convs.filter((c: any) => Number(c?.folder_id) === Number(activeFolderId));

  async function loadConversation(convId: number) {
    setActiveConvId(convId);
    convRef.current = String(convId);
    try {
      const r = await fetch(`/api/chat/conversations/${convId}/messages`, { credentials: 'include' });
      const j = await r.json().catch(() => ({} as any));
      const items = Array.isArray(j?.items) ? j.items : [];
      const mapped: Msg[] = items.map((m: any) => ({
        id: String(m?.id ?? crypto.randomUUID()),
        role: (String(m?.role) === 'ai' ? 'assistant' : 'user'),
        text: String(m?.text ?? ''),
        createdAt: (m?.created_at ?? m?.ts ?? null) || undefined,
      }));
      setMsgs(mapped);
    } catch {
      setMsgs([]);
    }
  }

  useEffect(() => {
    if (activeConvId == null) {
      setActiveConvFolderPick(null);
      return;
    }
    const cur = convs.find((c: any) => Number(c?.id) === Number(activeConvId));
    const fid = cur?.folder_id;
    setActiveConvFolderPick(fid == null ? null : Number(fid));
  }, [activeConvId, convs]);

  async function setActiveConversationFolder(folderId: number | null) {
    if (activeConvId == null) return;
    if (!foldersAvailable) return;
    try {
      await fetch(`/api/chat/conversations/${activeConvId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ folder_id: folderId }),
      });
      await refreshFolders();
      await refreshConversations();
      setActiveConvFolderPick(folderId);
      // Convenience: switch view to that folder when moving.
      if (folderId != null) setActiveFolderId(folderId);
    } catch {}
  }

  async function newConversation() {
    try {
      const r = await fetch('/api/chat/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ title: 'Neue Unterhaltung' }),
      });
      const j = await r.json().catch(() => ({} as any));
      const id = Number(j?.id ?? j?.conversation?.id);
      if (Number.isFinite(id) && id > 0) {
        setMsgs([]);
        setActiveConvId(id);
        convRef.current = String(id);
        await refreshConversations();
      }
    } catch {}
  }

  async function renameConversation(convId: number) {
    const cur = convs.find((c: any) => Number(c?.id) === Number(convId));
    const title = prompt('Neuer Titel', String(cur?.title ?? ''));
    if (!title) return;
    try {
      await fetch(`/api/chat/conversations/${convId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ title }),
      });
      await refreshConversations();
    } catch {}
  }

  async function removeConversationFromFolder(convId: number) {
    if (!foldersAvailable) return;
    try {
      await fetch(`/api/chat/conversations/${convId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ folder_id: null }),
      });
      await refreshFolders();
      await refreshConversations();
    } catch {}
  }

  async function moveConversationToFolder(convId: number, folderId: number | null) {
    if (!foldersAvailable) return;
    try {
      await fetch(`/api/chat/conversations/${convId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ folder_id: folderId }),
      });
      setMovePickerConvId(null);
      setMovePickerFolderId(null);
      await refreshFolders();
      await refreshConversations();
    } catch {}
  }

  async function deleteConversation(convId: number) {
    if (!confirm('Unterhaltung wirklich löschen?')) return;
    try {
      await fetch(`/api/chat/conversations/${convId}`, { method: 'DELETE', credentials: 'include' });
      if (activeConvId === convId) {
        setActiveConvId(null);
        convRef.current = null;
        setMsgs([]);
      }
      await refreshConversations();
    } catch {}
  }

  async function streamAnswer(payload: any) {
    if (startingStreamRef.current) return;
    startingStreamRef.current = true;

    finalizeSeenRef.current = false;
    activeRequestIdRef.current = String(payload?.request_id || '') || null;

    setStreamError(null);
    bufferRef.current = "";
    assistantIdRef.current = crypto.randomUUID();
    let finalized = false;
    let stop = false;
    let timeout: number | null = null;
    let controller: AbortController | null = null;
    let timeoutFired = false;
    const reqIdLocal = activeRequestIdRef.current;
    try {
      // Ensure a previous stream cannot leak state into a new one.
      try { activeControllerRef.current?.abort(); } catch {}
      const ctrl = new AbortController();
      controller = ctrl;
      activeControllerRef.current = ctrl;
      timeout = window.setTimeout(() => {
        timeoutFired = true;
        try { ctrl.abort(); } catch {}
      }, 60_000);
      const res = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
        credentials: 'include',
        cache: 'no-store',
        body: JSON.stringify(payload),
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) throw new Error('Stream start failed');

      setBusy(true);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        if (activeRequestIdRef.current !== reqIdLocal) {
          try { await reader.cancel(); } catch {}
          break;
        }
        const { value, done } = await reader.read();
        if (done) {
          // Some proxies/servers may close immediately after sending the last frame
          // without a trailing "\n\n". Best-effort: parse the leftover buffer once.
          if (finalizeSeenRef.current !== true) {
            try {
              const leftover = buffer;
              if (leftover && leftover.includes('data:')) {
                const dataLines = leftover
                  .split('\n')
                  .filter((l) => l.startsWith('data:'))
                  .map((l) => l.slice(5).trim());
                const payloadText = dataLines.join('\n');
                if (payloadText) {
                  const frame: any = JSON.parse(payloadText);
                  if (frame?.type === 'finalize' || frame?.done === true) {
                    finalized = true;
                    finalizeSeenRef.current = true;
                    if (activeRequestIdRef.current === reqIdLocal) {
                      setStreamError(null);
                    }
                    try {
                      const finConvId = Number(frame?.conversation_id ?? frame?.conv_id ?? 0);
                      if (Number.isFinite(finConvId) && finConvId > 0) {
                        convRef.current = String(finConvId);
                        if (activeRequestIdRef.current === reqIdLocal) {
                          setActiveConvId(finConvId);
                          refreshConversations();
                        }
                      }
                    } catch {}
                    const streamId = assistantIdRef.current || '__stream__';
                    if (activeRequestIdRef.current === reqIdLocal) {
                      setMsgs((prev) => {
                        const idxMsg = prev.findIndex((m) => m.id === streamId && m.role === 'assistant');
                        if (idxMsg < 0) return prev;
                        const clone = prev.slice();
                        const cur = clone[idxMsg];
                        const finalText = typeof frame?.text === 'string' && frame.text.length > 0
                          ? frame.text
                          : (bufferRef.current || cur.text);
                        clone[idxMsg] = {
                          ...cur,
                          text: finalText,
                          sources: Array.isArray(frame?.sources) ? frame.sources : (cur.sources ?? []),
                          memory_ids: Array.isArray(frame?.memory_ids) ? frame.memory_ids : (cur.memory_ids ?? []),
                          origin: typeof frame?.origin === 'string' ? frame.origin : cur.origin,
                          topic: typeof frame?.topic === 'string' ? frame.topic : cur.topic,
                          explain: frame?.explain ?? cur.explain,
                        };
                        return clone;
                      });
                    }
                    setBusy(false);
                    break;
                  }
                }
              }
            } catch {}
          }
          if (finalizeSeenRef.current === true) {
            // Finalize-wins: never overwrite finalize state with eof.
            break;
          }
          if (!finalized) {
            setStreamError('Stream beendet ohne finalize. Bitte erneut senden.');
          }
          break;
        }
        const chunkText = decoder
          .decode(value, { stream: true })
          .replace(/\r\n/g, '\n')
          .replace(/\r/g, '\n');
        buffer += chunkText;

        // Split SSE events by double newline (\n\n)
        while (buffer.includes('\n\n')) {
          const idx = buffer.indexOf('\n\n');
          const eventText = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);

          const dataLines = eventText
            .split('\n')
            .filter((l) => l.startsWith('data:'))
            .map((l) => l.slice(5).trim());

          const payloadText = dataLines.join('\n');
          if (!payloadText) continue;

          try {
            const frame: any = JSON.parse(payloadText);

            if (activeRequestIdRef.current !== reqIdLocal) {
              stop = true;
              break;
            }

            // Meta: carries request_id + conversation_id and must NOT be dropped.
            if (frame?.type === 'meta') {
              try {
                const metaConvId = Number(frame?.conversation_id ?? frame?.conv_id ?? 0);
                if (Number.isFinite(metaConvId) && metaConvId > 0) {
                  convRef.current = String(metaConvId);
                  if (activeRequestIdRef.current === reqIdLocal) {
                    setActiveConvId(metaConvId);
                    refreshConversations();
                  }
                }
              } catch {}
              continue;
            }

            // Ignore pure correlation frames.
            if (frame?.cid && !frame?.type && frame?.request_id == null) continue;

            // Handle deltas
            const deltaText =
              typeof frame?.delta === 'string' ? frame.delta :
              (frame?.type === 'delta' && typeof frame?.text === 'string' ? frame.text :
              '');

            if (deltaText) {
              bufferRef.current += deltaText;
              if (activeRequestIdRef.current !== reqIdLocal) {
                stop = true;
                break;
              }
              setMsgs((prev) => {
                const last = prev[prev.length - 1];
                const streamId = assistantIdRef.current || '__stream__';
                if (last && last.role === 'assistant' && last.id === streamId) {
                  const clone = prev.slice();
                  clone[clone.length - 1] = { ...last, text: bufferRef.current } as Msg;
                  return clone;
                }
                return [...prev, { id: streamId, role: 'assistant', text: bufferRef.current } as Msg];
              });
            }

            // Conversation id bootstrap
            const convIdCandidate = Number(frame?.conversation_id ?? frame?.conv_id ?? 0);
            if (!convRef.current && Number.isFinite(convIdCandidate) && convIdCandidate > 0) {
              convRef.current = String(convIdCandidate);
              if (activeRequestIdRef.current === reqIdLocal) {
                setActiveConvId(convIdCandidate);
                refreshConversations();
              }
            }

            // Finalize/done
            if (frame?.type === 'finalize' || frame?.done === true) {
              finalized = true;
              finalizeSeenRef.current = true;
              if (activeRequestIdRef.current === reqIdLocal) {
                setStreamError(null);
              }

              // Adopt conversation_id if provided and valid.
              try {
                const finConvId = Number(frame?.conversation_id ?? frame?.conv_id ?? 0);
                if (Number.isFinite(finConvId) && finConvId > 0) {
                  convRef.current = String(finConvId);
                  if (activeRequestIdRef.current === reqIdLocal) {
                    setActiveConvId(finConvId);
                    refreshConversations();
                  }
                }
              } catch {}

              const streamId = assistantIdRef.current || '__stream__';
              if (activeRequestIdRef.current !== reqIdLocal) {
                stop = true;
                break;
              }
              setMsgs((prev) => {
                const idxMsg = prev.findIndex((m) => m.id === streamId && m.role === 'assistant');
                if (idxMsg < 0) return prev;
                const clone = prev.slice();
                const cur = clone[idxMsg];
                const finalText = typeof frame?.text === 'string' && frame.text.length > 0
                  ? frame.text
                  : (bufferRef.current || cur.text);
                clone[idxMsg] = {
                  ...cur,
                  text: finalText,
                  sources: Array.isArray(frame?.sources) ? frame.sources : (cur.sources ?? []),
                  memory_ids: Array.isArray(frame?.memory_ids) ? frame.memory_ids : (cur.memory_ids ?? []),
                  origin: typeof frame?.origin === 'string' ? frame.origin : cur.origin,
                  topic: typeof frame?.topic === 'string' ? frame.topic : cur.topic,
                  explain: frame?.explain ?? cur.explain,
                };
                return clone;
              });

              try { await reader.cancel(); } catch {}
              setBusy(false);
              stop = true;
              break;
            }
          } catch {
            if (finalizeSeenRef.current === true) {
              // Finalize-wins
              stop = true;
              break;
            }
            if (activeRequestIdRef.current === reqIdLocal) {
              setStreamError('Stream Fehler. Bitte erneut senden.');
            }
          }
        }

        if (stop) break;
      }

      // If stream ends without a finalize frame, still reset UI state.
      if (!finalized) {
        if (finalizeSeenRef.current === true) {
          // Finalize-wins: ignore any post-finalize cleanup that could show eof/error.
          setBusy(false);
          return;
        }
        const streamId = assistantIdRef.current || '__stream__';
        setMsgs(prev => {
          const idx = prev.findIndex(m => m.id === streamId && m.role === 'assistant');
          if (idx < 0) return prev;
          const clone = prev.slice();
          clone[idx] = { ...clone[idx], text: bufferRef.current || clone[idx].text } as Msg;
          return clone;
        });
        setBusy(false);
      }
    } catch {
      if (finalizeSeenRef.current === true) {
        // Finalize-wins: do not show errors if we already received finalize.
        setBusy(false);
        return;
      }
      if (timeoutFired) {
        setStreamError('Stream timeout (60s). Bitte erneut senden.');
      } else {
        setStreamError('Stream abgebrochen. Bitte erneut senden.');
      }
      setBusy(false);
    } finally {
      if (timeout != null) {
        try { window.clearTimeout(timeout); } catch {}
      }
      try {
        if (controller && activeControllerRef.current === controller) {
          activeControllerRef.current = null;
        }
      } catch {}
      setBusy(false);
      startingStreamRef.current = false;
    }
  }

  function send() {
    const t = input.trim();
    if (!t || uiBusy) return;
    const userMsg: Msg = { id: crypto.randomUUID(), role: 'user', text: t, createdAt: Date.now() };
    setMsgs((m) => [...m, userMsg]);
    setInput('');
    const requestId = crypto.randomUUID();
    const convIdNum =
      typeof activeConvId === 'number' ? activeConvId :
      (convRef.current ? Number(convRef.current) : null);
    const convIdClean = (typeof convIdNum === 'number' && Number.isFinite(convIdNum) && convIdNum > 0)
      ? convIdNum
      : null;
    const payload = {
      message: t,
      conv_id: convIdClean,
      style: 'balanced',
      bullets: 5,
      web_ok: !!webOkAllowed,
      autonomy: 0,
      request_id: requestId,
    };
    streamAnswer(payload);
  }

  function onComposerKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="kiana-chat h-[calc(100vh-140px)] grid grid-cols-[280px_1fr]">
      <aside className="kiana-chat-sidebar p-3 overflow-y-auto">
        <div className="flex items-center justify-between">
          <div className="kiana-sidebar-brand">
            <span className="kiana-status-dot" aria-hidden />
            <div>
              <div className="kiana-sidebar-title">KI_ana</div>
              <div className="kiana-sidebar-sub">Online</div>
            </div>
          </div>
          <button className="kiana-btn kiana-btn-primary" onClick={newConversation} disabled={uiBusy}>＋ Neu</button>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2">
          <button
            className="kiana-btn"
            onClick={createFolder}
            disabled={uiBusy || !foldersAvailable}
            title={!foldersAvailable ? 'Ordner-Feature backendseitig nicht verfügbar' : 'Ordner erstellen'}
          >＋ Ordner</button>
          <button className="kiana-btn kiana-btn-ghost" onClick={refreshConversations} disabled={uiBusy}>↻ Refresh</button>
        </div>

        {foldersAvailable && activeConvId != null && (
          <div className="mt-3 p-3 rounded-xl border" style={{ borderColor: 'var(--k-border)', background: 'rgba(79,70,229,0.03)' }}>
            <div className="text-xs mb-1" style={{ color: 'var(--k-muted)' }}>Aktive Unterhaltung → Ordner</div>
            <div className="flex items-center gap-2">
              <select
                className="input"
                value={activeConvFolderPick == null ? '' : String(activeConvFolderPick)}
                onChange={(e) => {
                  const v = e.target.value;
                  const fid = v ? Number(v) : null;
                  setActiveConvFolderPick(fid);
                  setActiveConversationFolder(fid);
                }}
                disabled={uiBusy}
              >
                <option value="">(Ohne Ordner)</option>
                {folders.map((f: any) => (
                  <option key={f.id} value={String(f.id)}>{String(f.icon || '📁')} {String(f.name || 'Ordner')}</option>
                ))}
              </select>
              <button className="kiana-btn" disabled={uiBusy} onClick={() => setActiveConversationFolder(null)} title="Aus Ordner entfernen">↩</button>
            </div>
          </div>
        )}

        {!foldersAvailable && (
          <div className="mt-3 kiana-alert" style={{ padding: 12 }}>
            <div className="text-xs" style={{ color: 'var(--k-muted)' }}>
              Ordner sind aktuell nicht verfügbar.
            </div>
          </div>
        )}

        {foldersAvailable && (
        <div className="mt-3">
          <div className="flex items-center justify-between">
            <div className="text-xs mb-1" style={{ color: 'var(--k-muted)' }}>Ordner</div>
          </div>
          <div className="flex flex-col gap-1">
            <button
              className={`kiana-sidebar-item ${activeFolderId == null ? 'kiana-sidebar-item-active' : ''}`}
              onClick={() => setActiveFolderId(null)}
              disabled={uiBusy}
            >Alle</button>
            {folders.map((f: any) => (
              <div key={f.id} className={`flex items-center gap-2 ${Number(activeFolderId) === Number(f.id) ? 'kiana-sidebar-item-active' : ''}`} style={{ borderRadius: 999, padding: '6px 8px' }}>
                <button
                  className="flex-1 text-left truncate"
                  onClick={() => setActiveFolderId(Number(f.id))}
                  disabled={uiBusy}
                  title={String(f.name)}
                >{String(f.icon || '📁')} {String(f.name || 'Ordner')} <span className="opacity-60">({Number(f.conversation_count || 0)})</span></button>
                <button
                  className="text-xs"
                  style={{ color: 'var(--k-muted)' }}
                  onClick={() => moveActiveConversationToFolder(Number(f.id))}
                  disabled={uiBusy || !activeConvId}
                  title="Aktive Unterhaltung hier einsortieren"
                >↪</button>
                <button className="text-xs" style={{ color: 'var(--k-muted)' }} onClick={() => renameFolder(Number(f.id))} disabled={uiBusy} title="Umbenennen">✎</button>
                <button className="text-xs" style={{ color: 'var(--k-danger)' }} onClick={() => deleteFolder(Number(f.id))} disabled={uiBusy} title="Löschen">✕</button>
              </div>
            ))}
          </div>
        </div>
        )}
        <div className="mt-4">
          <div className="text-xs mb-1" style={{ color: 'var(--k-muted)' }}>Unterhaltungen</div>
          <div className="flex flex-col gap-1">
            {filteredConvs.map((c: any) => (
              <div key={c.id} className={`flex items-center gap-2 ${Number(activeConvId) === Number(c.id) ? 'kiana-sidebar-item-active' : ''}`} style={{ borderRadius: 999, padding: '6px 8px' }}>
                <button className="flex-1 text-left truncate" onClick={() => loadConversation(Number(c.id))} disabled={uiBusy}>
                  {String(c.title || 'Unterhaltung')}
                </button>
                {foldersAvailable && (
                  <>
                    <button
                      className="text-xs opacity-70"
                      onClick={() => {
                        const cid = Number(c.id);
                        setMovePickerConvId((cur) => (cur === cid ? null : cid));
                        setMovePickerFolderId(null);
                      }}
                      disabled={uiBusy}
                      title="In Ordner verschieben"
                    >↪</button>
                    {c?.folder_id != null && (
                      <button className="text-xs opacity-70" onClick={() => removeConversationFromFolder(Number(c.id))} disabled={uiBusy} title="Aus Ordner entfernen">↩</button>
                    )}
                  </>
                )}
                <button className="text-xs opacity-70" onClick={() => renameConversation(Number(c.id))} disabled={uiBusy} title="Umbenennen">✎</button>
                <button className="text-xs" style={{ color: 'var(--k-danger)' }} onClick={() => deleteConversation(Number(c.id))} disabled={uiBusy} title="Löschen">✕</button>
              </div>
            ))}
            {foldersAvailable && movePickerConvId != null && (
              <div className="px-2 py-2 text-xs border border-gray-200 dark:border-gray-800 rounded">
                <div className="opacity-80 mb-2">In Ordner verschieben</div>
                <div className="flex items-center gap-2">
                  <select
                    className="input"
                    value={movePickerFolderId == null ? '' : String(movePickerFolderId)}
                    onChange={(e) => {
                      const v = e.target.value;
                      setMovePickerFolderId(v ? Number(v) : null);
                    }}
                      disabled={uiBusy}
                  >
                    <option value="">(Ordner wählen)</option>
                    {folders.map((f: any) => (
                      <option key={f.id} value={String(f.id)}>{String(f.icon || '📁')} {String(f.name || 'Ordner')}</option>
                    ))}
                  </select>
                  <button
                    className="kiana-btn"
                    disabled={uiBusy || movePickerFolderId == null}
                    onClick={() => moveConversationToFolder(Number(movePickerConvId), Number(movePickerFolderId))}
                  >Verschieben</button>
                  <button className="kiana-btn" disabled={uiBusy} onClick={() => setMovePickerConvId(null)}>Abbrechen</button>
                </div>
              </div>
            )}
            {filteredConvs.length === 0 && <div className="text-xs opacity-60 px-2 py-2">Keine Unterhaltungen</div>}
          </div>
        </div>

        {streamError && (
          <div className="mt-4 p-3 rounded-xl border" style={{ borderColor: 'rgba(220,38,38,0.25)', background: 'rgba(220,38,38,0.06)', color: 'var(--k-danger)' }}>
            <div className="text-sm">{streamError}</div>
          </div>
        )}
      </aside>

      <div className="kiana-chat-main grid grid-rows-[auto_1fr_auto]">
      <div className="kiana-chat-header">
        <img className="kiana-chat-avatar" src="/static/Avatar_KI_ana.png" alt="KI_ana" />
        <div className="kiana-chat-header-info">
          <div className="kiana-chat-title">KI_ana</div>
          <div className="kiana-chat-sub">Chat</div>
        </div>

        <div className="flex-1" />

        {canExplain && (
          <label className="kiana-switch text-sm">
            <input
              type="checkbox"
              checked={showExplain}
              onChange={(e) => {
                const v = e.target.checked;
                setShowExplain(v);
                try { localStorage.setItem('kiana_show_explain', v ? '1' : '0'); } catch {}
              }}
              disabled={!canExplain}
            />
            Explain
          </label>
        )}
      </div>

      <div ref={scrollerRef} className="kiana-chat-messages overflow-y-auto p-4 flex flex-col gap-3">
        {msgs.length === 0 ? (
          <div className="card text-center">
            <div className="text-2xl">Hallo 👋 Schön, dass du wieder da bist!</div>
            <div className="small mt-2">Stell eine Frage oder beschreibe deine Aufgabe.</div>
          </div>
        ) : (
          msgs.map((m) => (
            <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`kiana-bubble ${m.role === 'user' ? 'kiana-bubble-user' : 'kiana-bubble-ai'}`}>
                <div className="whitespace-pre-wrap">{m.text}</div>
                <div className="kiana-bubble-meta">
                  <span className="kiana-bubble-time">
                    {(() => {
                      try {
                        const d = typeof m.createdAt === 'number' ? new Date(m.createdAt) : (m.createdAt ? new Date(String(m.createdAt)) : null);
                        return d ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
                      } catch {
                        return '';
                      }
                    })()}
                  </span>
                  {canShowExplainUi && m.role === 'assistant' && (m.explain || (m.sources && m.sources.length) || (m.memory_ids && m.memory_ids.length)) && (
                    <button
                      type="button"
                      className="kiana-explain-btn"
                      title="Explain"
                      onClick={() => setExplainOpenMsgId(m.id)}
                    >ⓘ</button>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
        {uiBusy && (
          <div className="flex justify-start"><div className="kiana-bubble kiana-bubble-ai opacity-90">KI_ana denkt …</div></div>
        )}
      </div>
      <div className="kiana-chat-composer p-3" style={{ borderTop: '1px solid var(--k-border)' }}>
        <div className="max-w-4xl mx-auto flex gap-2 items-center">
          <textarea
            className="kiana-composer-input flex-1 resize-none"
            placeholder="Nachricht eingeben…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onComposerKey}
            disabled={uiBusy}
            rows={1}
          />
          <button className="kiana-composer-send" onClick={send} disabled={uiBusy}>Senden</button>
        </div>
      </div>

      {explainOpenMsg && (
        <div
          className="fixed inset-0 z-[1000] flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          onClick={() => setExplainOpenMsgId(null)}
        >
          <div className="absolute inset-0 bg-black/40" />
          <div className="kiana-modal p-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between gap-3">
              <div className="font-semibold">Explain</div>
              <button className="kiana-btn" onClick={() => setExplainOpenMsgId(null)}>Schließen</button>
            </div>
            <div className="mt-3 text-xs">
              {(() => {
                const ex = (explainOpenMsg as any).explain || {};
                const intent = typeof ex.intent === 'string' ? ex.intent : '';
                const route = typeof ex.route === 'string' ? ex.route : '';
                const totalMs = ex?.timings_ms && typeof ex.timings_ms.total === 'number' ? ex.timings_ms.total : null;
                const toolsArr = Array.isArray(ex.tools) ? ex.tools : [];
                const okCount = toolsArr.filter((t: any) => t && t.ok === true).length;
                const errCount = toolsArr.filter((t: any) => t && t.ok === false).length;
                return (
                  <div className="opacity-90">
                    {(intent || route || totalMs !== null) && (
                      <div className="opacity-80">
                        {intent ? <div>intent: {intent}</div> : null}
                        {route ? <div>route: {route}</div> : null}
                        {totalMs !== null ? <div>total_ms: {totalMs}</div> : null}
                      </div>
                    )}
                    {toolsArr.length > 0 && (
                      <div className="opacity-80 mt-1">tools: {okCount} ok / {errCount} error</div>
                    )}
                  </div>
                );
              })()}
              <pre className="mt-3 text-xs whitespace-pre-wrap">{JSON.stringify({
                topic: (explainOpenMsg as any).topic,
                origin: (explainOpenMsg as any).origin,
                memory_ids: (explainOpenMsg as any).memory_ids,
                sources: (explainOpenMsg as any).sources,
                explain: (explainOpenMsg as any).explain,
              }, null, 2)}</pre>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}
