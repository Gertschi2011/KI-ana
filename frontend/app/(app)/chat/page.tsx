"use client";
import { useEffect, useRef, useState } from 'react';

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
  const [sseLastEventType, setSseLastEventType] = useState<string>('');
  const [sseReceivedBytes, setSseReceivedBytes] = useState<number>(0);
  const [sseLastFramePreview, setSseLastFramePreview] = useState<string>('');
  const [sseLastRequestId, setSseLastRequestId] = useState<string>('');
  const [sseLastRequestConvId, setSseLastRequestConvId] = useState<string>('');
  const [sseLastRequestMessage, setSseLastRequestMessage] = useState<string>('');
  const [folders, setFolders] = useState<any[]>([]);
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
        const isAdmin = !!u?.is_admin || (Array.isArray(u?.roles) && u.roles.includes('admin'));
        const isCreator = !!u?.is_creator || (Array.isArray(u?.roles) && u.roles.includes('creator'));
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
      const j = await r.json().catch(() => ({} as any));
      setFolders(Array.isArray(j?.folders) ? j.folders : []);
    } catch {
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
    if (!confirm('Ordner wirklich löschen? (Unterhaltungen bleiben erhalten)')) return;
    try {
      await fetch(`/api/folders/${folderId}`, { method: 'DELETE', credentials: 'include' });
      if (Number(activeFolderId) === Number(folderId)) setActiveFolderId(null);
      await refreshFolders();
      await refreshConversations();
    } catch {}
  }

  async function moveActiveConversationToFolder(folderId: number) {
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
    setSseLastEventType('');
    setSseReceivedBytes(0);
    setSseLastFramePreview('');
    setSseLastRequestId(String(payload?.request_id || ''));
    setSseLastRequestConvId(payload?.conv_id != null ? String(payload.conv_id) : '');
    setSseLastRequestMessage(String(payload?.message || '').slice(0, 160));
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
          console.log('SSE end');
          if (finalizeSeenRef.current === true) {
            // Finalize-wins: never overwrite finalize state with eof.
            break;
          }
          if (!finalized) {
            setSseLastEventType('eof');
            setStreamError('Stream beendet ohne finalize. Bitte erneut senden.');
          }
          break;
        }
        const chunkText = decoder
          .decode(value, { stream: true })
          .replace(/\r\n/g, '\n')
          .replace(/\r/g, '\n');
        console.log('SSE chunk', chunkText);
        if (activeRequestIdRef.current === reqIdLocal) {
          setSseReceivedBytes((b) => b + (value?.byteLength || 0));
        }

        buffer += chunkText;

        // Split SSE events by double newline (\n\n)
        while (buffer.includes('\n\n')) {
          const idx = buffer.indexOf('\n\n');
          const eventText = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);

          const preview = eventText.length > 240 ? `${eventText.slice(0, 240)}…` : eventText;
          if (activeRequestIdRef.current === reqIdLocal) {
            setSseLastFramePreview(preview);
          }

          const dataLines = eventText
            .split('\n')
            .filter((l) => l.startsWith('data:'))
            .map((l) => l.slice(5).trim());

          const payloadText = dataLines.join('\n');
          if (!payloadText) continue;

          try {
            const frame: any = JSON.parse(payloadText);
            console.log('SSE frame', frame);

            if (activeRequestIdRef.current !== reqIdLocal) {
              stop = true;
              break;
            }

            const typeGuess =
              typeof frame?.type === 'string' ? frame.type :
              frame?.done === true ? 'done' :
              frame?.delta ? 'delta' :
              'event';
            if (activeRequestIdRef.current === reqIdLocal) {
              setSseLastEventType(typeGuess);
            }

            if (frame?.cid) continue; // correlation id

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
            const convId = frame?.conv_id ?? frame?.conversation_id;
            if (convId && !convRef.current) {
              convRef.current = String(convId);
              const cid = Number(convId);
              if (activeRequestIdRef.current === reqIdLocal) {
                if (Number.isFinite(cid)) setActiveConvId(cid);
                refreshConversations();
              }
            }

            // Finalize/done
            if (frame?.type === 'finalize' || frame?.done === true) {
              finalized = true;
              finalizeSeenRef.current = true;
              if (activeRequestIdRef.current === reqIdLocal) {
                setSseLastEventType('finalize');
                setStreamError(null);
              }
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
                  sources: Array.isArray(frame?.sources) ? frame.sources : cur.sources,
                  memory_ids: Array.isArray(frame?.memory_ids) ? frame.memory_ids : cur.memory_ids,
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
          } catch (err) {
            console.error('SSE error', err);
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
    } catch (e) {
      console.error('SSE error', e);
      if (finalizeSeenRef.current === true) {
        // Finalize-wins: do not show errors if we already received finalize.
        setBusy(false);
        return;
      }
      if (timeoutFired) {
        setSseLastEventType('timeout');
        setStreamError('Stream timeout (60s). Bitte erneut senden.');
      } else {
        try {
          if (controller?.signal?.aborted) {
            setSseLastEventType('aborted');
          }
        } catch {}
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
    const payload = {
      message: t,
      conv_id: Number.isFinite(Number(convIdNum)) ? Number(convIdNum) : null,
      style: 'balanced',
      bullets: 5,
      web_ok: !!webOkAllowed,
      autonomy: 0,
      request_id: requestId,
    };
    streamAnswer(payload);
  }

  function onKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="kiana-chat h-[calc(100vh-140px)] grid grid-cols-[280px_1fr]">
      <aside className="kiana-chat-sidebar p-3 overflow-y-auto">
        <div className="flex items-center justify-between">
          <div className="font-semibold">Unterhaltungen</div>
          <button className="btn-dark" onClick={newConversation} disabled={uiBusy}>Neu</button>
        </div>

        {activeConvId != null && (
          <div className="mt-3 p-2 rounded border border-gray-200 dark:border-gray-800">
            <div className="text-xs opacity-70 mb-1">Aktive Unterhaltung → Ordner</div>
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
              <button className="btn-dark" disabled={uiBusy} onClick={() => setActiveConversationFolder(null)} title="Aus Ordner entfernen">↩</button>
            </div>
          </div>
        )}

        <div className="mt-3">
          <div className="flex items-center justify-between">
            <div className="text-xs opacity-70 mb-1">Ordner</div>
            <button className="text-xs opacity-70 hover:opacity-100" onClick={createFolder} disabled={uiBusy} title="Ordner erstellen">＋</button>
          </div>
          <div className="flex flex-col gap-1">
            <button
              className={`text-left px-2 py-1 rounded ${activeFolderId == null ? 'bg-gray-200 dark:bg-gray-800' : 'hover:bg-gray-100 dark:hover:bg-gray-900'}`}
              onClick={() => setActiveFolderId(null)}
              disabled={uiBusy}
            >Alle</button>
            {folders.map((f: any) => (
              <div key={f.id} className={`flex items-center gap-2 px-2 py-1 rounded ${Number(activeFolderId) === Number(f.id) ? 'bg-gray-200 dark:bg-gray-800' : 'hover:bg-gray-100 dark:hover:bg-gray-900'}`}>
                <button
                  className="flex-1 text-left truncate"
                  onClick={() => setActiveFolderId(Number(f.id))}
                  disabled={uiBusy}
                  title={String(f.name)}
                >{String(f.icon || '📁')} {String(f.name || 'Ordner')} <span className="opacity-60">({Number(f.conversation_count || 0)})</span></button>
                <button className="text-xs opacity-70" onClick={() => moveActiveConversationToFolder(Number(f.id))} disabled={uiBusy || !activeConvId} title="Aktive Unterhaltung hier einsortieren">↪</button>
                <button className="text-xs opacity-70" onClick={() => renameFolder(Number(f.id))} disabled={uiBusy} title="Umbenennen">✎</button>
                <button className="text-xs opacity-70" onClick={() => deleteFolder(Number(f.id))} disabled={uiBusy} title="Löschen">✕</button>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-4">
          <div className="text-xs opacity-70 mb-1">Chats</div>
          <div className="flex flex-col gap-1">
            {filteredConvs.map((c: any) => (
              <div key={c.id} className={`flex items-center gap-2 px-2 py-1 rounded ${Number(activeConvId) === Number(c.id) ? 'bg-gray-200 dark:bg-gray-800' : 'hover:bg-gray-100 dark:hover:bg-gray-900'}`}>
                <button className="flex-1 text-left truncate" onClick={() => loadConversation(Number(c.id))} disabled={uiBusy}>
                  {String(c.title || 'Unterhaltung')}
                </button>
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
                <button className="text-xs opacity-70" onClick={() => renameConversation(Number(c.id))} disabled={uiBusy} title="Umbenennen">✎</button>
                <button className="text-xs opacity-70" onClick={() => deleteConversation(Number(c.id))} disabled={uiBusy} title="Löschen">✕</button>
              </div>
            ))}
            {movePickerConvId != null && (
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
                    className="btn-dark"
                    disabled={uiBusy || movePickerFolderId == null}
                    onClick={() => moveConversationToFolder(Number(movePickerConvId), Number(movePickerFolderId))}
                  >Verschieben</button>
                  <button className="btn-dark" disabled={uiBusy} onClick={() => setMovePickerConvId(null)}>Abbrechen</button>
                </div>
              </div>
            )}
            {filteredConvs.length === 0 && <div className="text-xs opacity-60 px-2 py-2">Keine Unterhaltungen</div>}
          </div>
        </div>

        <div className="mt-5 pt-4 border-t border-gray-200 dark:border-gray-800">
          <div className="text-xs opacity-70 mb-2">Settings</div>
          <label className="flex items-center gap-2 text-sm">
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
            Explain anzeigen
          </label>
          {!canExplain && <div className="text-xs opacity-60 mt-1">Explain nur für creator/admin</div>}
          {streamError && <div className="text-xs text-red-600 mt-2">{streamError}</div>}
        </div>
      </aside>

      <div className="kiana-chat-main grid grid-rows-[auto_1fr_auto]">
      <div className="kiana-chat-header">
        <img className="kiana-chat-avatar" src="/static/Avatar_KI_ana.png" alt="KI_ana" />
        <div className="kiana-chat-header-info">
          <div className="kiana-chat-title">KI_ana</div>
          <div className="kiana-chat-sub">Online &amp; bereit</div>
        </div>
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
                  {showExplain && canExplain && m.role === 'assistant' && (m.explain || (m.sources && m.sources.length) || (m.memory_ids && m.memory_ids.length)) && (
                    <button
                      type="button"
                      className="kiana-explain-btn"
                      title="Explain"
                      onClick={() => setExplainOpenMsgId(m.id)}
                    >ⓘ Explain</button>
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
      <div className="kiana-chat-composer border-t border-gray-200 dark:border-gray-800 p-3">
        <div className="max-w-4xl mx-auto flex gap-2 items-center">
          <input
            className="kiana-composer-input flex-1"
            placeholder="Nachricht eingeben…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKey}
            disabled={uiBusy}
          />
          <button className="kiana-composer-send" onClick={send} disabled={uiBusy}>Senden</button>
        </div>
        <div className="max-w-4xl mx-auto mt-2 text-xs opacity-80">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <div className="px-2 py-1 rounded border border-gray-200 dark:border-gray-800">
              <div className="opacity-70">lastEventType</div>
              <div className="font-mono break-all">{sseLastEventType || '-'}</div>
            </div>
            <div className="px-2 py-1 rounded border border-gray-200 dark:border-gray-800">
              <div className="opacity-70">receivedBytes</div>
              <div className="font-mono">{sseReceivedBytes}</div>
            </div>
            <div className="px-2 py-1 rounded border border-gray-200 dark:border-gray-800">
              <div className="opacity-70">lastFramePreview</div>
              <div className="font-mono break-all">{sseLastFramePreview || '-'}</div>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mt-2">
            <div className="px-2 py-1 rounded border border-gray-200 dark:border-gray-800">
              <div className="opacity-70">request_id</div>
              <div className="font-mono break-all">{sseLastRequestId || '-'}</div>
            </div>
            <div className="px-2 py-1 rounded border border-gray-200 dark:border-gray-800">
              <div className="opacity-70">conv_id</div>
              <div className="font-mono break-all">{sseLastRequestConvId || '-'}</div>
            </div>
            <div className="px-2 py-1 rounded border border-gray-200 dark:border-gray-800">
              <div className="opacity-70">message</div>
              <div className="font-mono break-all">{sseLastRequestMessage || '-'}</div>
            </div>
          </div>
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
          <div
            className="relative w-full max-w-3xl max-h-[80vh] overflow-auto rounded-xl bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="font-semibold">Explain</div>
              <button className="btn-dark" onClick={() => setExplainOpenMsgId(null)}>Schließen</button>
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
