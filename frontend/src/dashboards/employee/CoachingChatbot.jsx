import React, { useState } from 'react';

const TOPICS = [
  { id: 'skills', label: 'Sharpen my skills' },
  { id: 'role', label: 'Understand my role' },
  { id: 'career', label: 'Career path' },
  { id: 'compliance', label: 'Compliance' },
  { id: 'wellbeing', label: 'Stress & wellbeing' },
  { id: 'prioritization', label: 'Time & priorities' },
];

export default function CoachingChatbot() {
  const [topic, setTopic] = useState('skills');
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hi! I can help you practise a skill, understand your role, explore development goals, manage priorities, or think through work stress. What would you like to work on?' },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSend = async (event) => {
    event.preventDefault();
    const content = input.trim();
    if (!content || loading) return;

    const nextMessages = [...messages, { role: 'user', content }];
    setMessages(nextMessages);
    setInput('');
    setLoading(true);
    setError('');

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('http://127.0.0.1:8000/api/v1/coaching/chat', {
        method: 'POST',
        headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, messages: nextMessages.slice(-12) }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'The coach could not respond.');
      setMessages((current) => [...current, { role: 'assistant', content: data.reply }]);
    } catch (sendError) {
      setError(sendError.message || 'The coach could not respond. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="space-y-4">
      <div className="rounded-lg border border-blue-100 bg-blue-50 p-4 text-sm text-blue-900">
        This coach supports learning and reflection; it does not make employment decisions or replace your manager,
        Compliance team, or a health professional. Please do not share customer or account details.
      </div>
      <div className="flex flex-wrap gap-2" aria-label="Coaching topics">
        {TOPICS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTopic(item.id)}
            aria-pressed={topic === item.id}
            className={'rounded-full border px-3 py-2 text-sm font-semibold transition ' + (
              topic === item.id
                ? 'border-blue-700 bg-blue-700 text-white'
                : 'border-slate-300 bg-white text-slate-700 hover:border-blue-400'
            )}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="flex h-[440px] flex-col rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex-1 space-y-3 overflow-y-auto p-4" aria-live="polite">
          {messages.map((message, index) => (
            <div key={message.role + '-' + index} className={'flex ' + (message.role === 'user' ? 'justify-end' : 'justify-start')}>
              <div className={'max-w-[85%] whitespace-pre-wrap rounded-xl px-4 py-3 text-sm leading-relaxed ' + (
                message.role === 'user'
                  ? 'bg-blue-700 text-white'
                  : 'border border-slate-200 bg-slate-50 text-slate-800'
              )}>
                {message.content}
              </div>
            </div>
          ))}
          {loading && <p className="text-sm text-slate-500" role="status">Your coach is preparing a response…</p>}
        </div>
        {error && <p className="mx-4 mb-2 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">{error}</p>}
        <form onSubmit={handleSend} className="flex gap-2 border-t border-slate-200 p-3">
          <label className="sr-only" htmlFor="coaching-message">Your message</label>
          <input
            id="coaching-message"
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            maxLength={2000}
            placeholder="What would you like help with?"
            className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-bold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            Send
          </button>
        </form>
      </div>
    </section>
  );
}