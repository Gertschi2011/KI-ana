"use client";
import { useEffect, useRef, useState } from 'react';

type Msg = { id: string; role: 'user' | 'assistant'; text: string };

export default function ChatPage() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const scrollerRef = useRef<HTMLDivElement>(null);
  const convRef = useRef<string | null>(null);
  const bufferRef = useRef<string>("");

  useEffect(() => {
    scrollerRef.current?.scrollTo({ top: scrollerRef.current.scrollHeight });
  }, [msgs.length, busy]);

  async function streamAnswer(payload: any) {
    setBusy(true);
    bufferRef.current = "";
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
                if (last && last.role === 'assistant' && last.id === '__stream__') {
                  const clone = prev.slice();
                  clone[clone.length - 1] = { ...last, text: bufferRef.current } as Msg;
                  return clone;
                }
                return [...prev, { id: '__stream__', role: 'assistant', text: bufferRef.current } as Msg];
              });
            }
            if (evt.conv_id && !convRef.current) {
              convRef.current = String(evt.conv_id);
            }
            if (evt.done) {
              setBusy(false);
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
              <div className={`bubble ${m.role === 'user' ? 'bubble-user' : 'bubble-bot'}`}>{m.text}</div>
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
