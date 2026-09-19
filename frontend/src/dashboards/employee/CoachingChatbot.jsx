import React, { useState } from 'react';

export default function CoachingChatbot({ latestScore }) {
  const [messages, setMessages] = useState([
    {
      sender: 'bot',
      text: `Welcome! I'm your AI Performance Coach. Your latest score is ${latestScore ?? 'pending submission'}. How can I help you optimize your metrics today?`
    }
  ]);
  const [input, setInput] = useState('');

  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMsg = { sender: 'user', text: input };
    setMessages((prev) => [...prev, userMsg]);

    // Simulated contextual response logic
    setTimeout(() => {
      let botText = "Focusing on reducing transaction error frequency will deliver the highest boost to your TrustScore.";
      if (input.toLowerCase().includes('accuracy')) {
        botText = "Maintaining a transaction accuracy score above 95% triggers positive weights in the Random Forest evaluation model.";
      } else if (input.toLowerCase().includes('volume')) {
        botText = "Loan volume counts are regularized against branch averages to ensure equitable evaluation.";
      }

      setMessages((prev) => [...prev, { sender: 'bot', text: botText }]);
    }, 600);

    setInput('');
  };

  return (
    <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 shadow-md flex flex-col h-[480px]">
      <h3 className="text-lg font-bold text-teal-400 mb-3">AI Coaching Chatbot</h3>
      
      <div className="flex-1 overflow-y-auto space-y-3 p-3 bg-slate-900 rounded-lg mb-3">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-lg p-3 text-sm ${msg.sender === 'user' ? 'bg-teal-600 text-white' : 'bg-slate-800 text-slate-200 border border-slate-700'}`}>
              {msg.text}
            </div>
          </div>
        ))}
      </div>

      <form onSubmit={handleSend} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask for performance coaching advice..."
          className="flex-1 bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-sm text-slate-100 focus:outline-none focus:border-teal-500"
        />
        <button type="submit" className="bg-teal-500 hover:bg-teal-600 text-slate-950 font-bold px-4 py-2 rounded-lg text-sm">
          Send
        </button>
      </form>
    </div>
  );
}