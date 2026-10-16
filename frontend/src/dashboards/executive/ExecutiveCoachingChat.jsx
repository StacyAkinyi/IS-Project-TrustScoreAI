import React, { useState } from 'react';

export default function ExecutiveCoachingChat({ executiveId }) {
  const [messages, setMessages] = useState([{ role: 'assistant', content: 'I can help review regional KPI patterns and think through supportive next steps. I use employee telemetry within your oversight region and treat the color bands as demonstration thresholds, not policy.' }]);
  const [input, setInput] = useState(''); const [loading, setLoading] = useState(false); const [error, setError] = useState('');
  const send = async (event) => {
    event.preventDefault(); const content = input.trim(); if (!content || loading) return;
    const next = [...messages, { role: 'user', content }]; setMessages(next); setInput(''); setLoading(true); setError('');
    try {
      const response = await fetch(`http://127.0.0.1:8000/api/v1/executives/${executiveId}/coaching/chat`, { method: 'POST', headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ messages: next.slice(-12) }) });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail || 'The executive coach could not answer.');
      setMessages((current) => [...current, { role: 'assistant', content: data.reply }]);
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  };
  return <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="text-lg font-bold text-blue-900">Regional coaching assistant</h3><p className="mt-1 text-xs text-slate-500">Uses your region’s latest KPI data. Metrics can flag a question to explore; they do not explain causes or make employment decisions.</p><div className="mt-4 h-72 space-y-3 overflow-y-auto rounded-lg bg-slate-50 p-3" aria-live="polite">{messages.map((m, i) => <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}><p className={`max-w-[85%] whitespace-pre-wrap rounded-xl px-3 py-2 text-sm ${m.role === 'user' ? 'bg-blue-700 text-white' : 'bg-white text-slate-800 shadow-sm'}`}>{m.content}</p></div>)}{loading && <p className="text-sm text-slate-500">Reviewing regional context…</p>}</div>{error && <p role="alert" className="mt-2 rounded bg-rose-50 p-2 text-sm text-rose-700">{error}</p>}<form onSubmit={send} className="mt-3 flex gap-2"><input value={input} onChange={(e) => setInput(e.target.value)} maxLength={2000} placeholder="Ask about a regional KPI pattern…" className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm" /><button disabled={loading || !input.trim()} className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-bold text-white disabled:bg-slate-400">Send</button></form></section>;
}
