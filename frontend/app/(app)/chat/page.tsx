"use client";
import { useEffect, useRef, useState } from 'react';

type Msg = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
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
  const [canExplain, setCanExplain] = useState(false);
  const scrollerRef = useRef<HTMLDivElement>(null);
  const convRef = useRef<string | null>(null);
  const bufferRef = useRef<string>("");
  const assistantIdRef = useRef<string | null>(null);

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

  async function streamAnswer(payload: any) {
    setBusy(true);
    bufferRef.current = "";
    assistantIdRef.current = crypto.randomUUID();
    try {
      const res = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok || !res.body) throw new Error('Stream start failed');
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let carry = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        carry += chunk;
        // Split SSE frames by double newline
        const parts = carry.split(/\n\n/);
        carry = parts.pop() || '';
        for (const part of parts) {
          const line = part.split('\n').find(l => l.startsWith('data: '));
          if (!line) continue;
          const json = line.slice(6);
          try {
            const evt = JSON.parse(json);
            if (evt.cid) continue; // correlation id
            if (evt.delta) {
              bufferRef.current += evt.delta;
              // show partial in UI as one assistant bubble
              setMsgs(prev => {
                // If last is assistant placeholder, update it; else append new
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
            if (evt.conv_id && !convRef.current) {
              convRef.current = String(evt.conv_id);
            }
            // Finalize payload may include full text + meta
            if (evt.done) {
              const streamId = assistantIdRef.current || '__stream__';
              setMsgs(prev => {
                const idx = prev.findIndex(m => m.id === streamId && m.role === 'assistant');
                if (idx < 0) return prev;
                const clone = prev.slice();
                const cur = clone[idx];
                const finalText = typeof evt.text === 'string' && evt.text.length > 0
                  ? evt.text
                  : (bufferRef.current || cur.text);
                clone[idx] = {
                  ...cur,
                  text: finalText,
                  sources: Array.isArray(evt.sources) ? evt.sources : cur.sources,
                  memory_ids: Array.isArray(evt.memory_ids) ? evt.memory_ids : cur.memory_ids,
                  origin: typeof evt.origin === 'string' ? evt.origin : cur.origin,
                  topic: typeof evt.topic === 'string' ? evt.topic : cur.topic,
                  explain: evt.explain ?? cur.explain,
                };
                return clone;
              });
              setBusy(false);
            }
            if (evt.done) {
              // already handled above
            }
          } catch {}
        }
      }
    } catch (e) {
      setBusy(false);
    }
  }

  function send() {
    const t = input.trim();
    if (!t || busy) return;
    const userMsg: Msg = { id: crypto.randomUUID(), role: 'user', text: t };
    setMsgs((m) => [...m, userMsg]);
    setInput('');
    const payload = {
      message: t,
      conv_id: convRef.current,
      style: 'balanced',
      bullets: 5,
      web_ok: false,
      autonomy: 0,
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
    <div className="h-[calc(100vh-140px)] grid grid-rows-[1fr_auto]">
      <div ref={scrollerRef} className="overflow-y-auto p-4 flex flex-col gap-3">
        {msgs.length === 0 ? (
          <div className="card text-center">
            <div className="text-2xl">Hallo 👋 Schön, dass du wieder da bist!</div>
            <div className="small mt-2">Stell eine Frage oder beschreibe deine Aufgabe.</div>
          </div>
        ) : (
          msgs.map((m) => (
            <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`bubble ${m.role === 'user' ? 'bubble-user' : 'bubble-bot'}`}>
                <div className="whitespace-pre-wrap">{m.text}</div>
                {canExplain && m.role === 'assistant' && (m.explain || (m.sources && m.sources.length) || (m.memory_ids && m.memory_ids.length)) && (
                  <details className="mt-2">
                    <summary className="text-xs opacity-70 cursor-pointer select-none">Explain</summary>
                    {(() => {
                      const ex = m.explain || {};
                      const intent = typeof ex.intent === 'string' ? ex.intent : '';
                      const route = typeof ex.route === 'string' ? ex.route : '';
                      const totalMs = ex?.timings_ms && typeof ex.timings_ms.total === 'number' ? ex.timings_ms.total : null;
                      const toolsArr = Array.isArray(ex.tools) ? ex.tools : [];
                      const okCount = toolsArr.filter((t: any) => t && t.ok === true).length;
                      const errCount = toolsArr.filter((t: any) => t && t.ok === false).length;
                      return (
                        <div className="text-xs mt-2">
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
                    <pre className="text-xs whitespace-pre-wrap mt-2">{JSON.stringify({
                      topic: m.topic,
                      origin: m.origin,
                      memory_ids: m.memory_ids,
                      sources: m.sources,
                      explain: m.explain,
                    }, null, 2)}</pre>
                  </details>
                )}
              </div>
            </div>
          ))
        )}
        {busy && (
          <div className="flex justify-start"><div className="bubble bubble-bot opacity-80">KI_ana denkt …</div></div>
        )}
      </div>
      <div className="border-t border-gray-200 dark:border-gray-800 p-3">
        <div className="max-w-4xl mx-auto flex gap-2">
          <input
            className="input flex-1"
            placeholder="Nachricht eingeben…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKey}
            disabled={busy}
          />
          <button className="btn-dark" onClick={send} disabled={busy}>Senden</button>
        </div>
      </div>
    </div>
  );
}
