import React, { useState } from 'react';

const API = 'http://127.0.0.1:8000/api/v1';
const resetToken = new URLSearchParams(window.location.search).get('reset_token');

export default function Login({ onLogin }) {
  const [view, setView] = useState(resetToken ? 'reset' : 'login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const changeView = (next) => { setView(next); setError(''); setMessage(''); };
  const request = async (path, body) => {
    const response = await fetch(API + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Request failed.');
    return data;
  };

  const submit = async (event) => {
    event.preventDefault();
    setError(''); setMessage(''); setBusy(true);
    try {
      if (view === 'login') {
        const data = await request('/login', { email: email.trim(), password });
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('user_role', data.role);
        localStorage.setItem('user_id', String(data.user_id));
        localStorage.setItem('user_email', data.email);
        onLogin(data.role);
      } else if (view === 'forgot') {
        const data = await request('/forgot-password', { email: email.trim() });
        setMessage(data.message);
      } else {
        if (newPassword !== confirmPassword) throw new Error('The passwords do not match.');
        const data = await request('/reset-password', { token: resetToken, new_password: newPassword });
        window.history.replaceState({}, document.title, window.location.pathname);
        setMessage(data.message);
        setNewPassword(''); setConfirmPassword('');
        setView('login');
      }
    } catch (err) {
      setError(err.message || 'Could not connect to the API. Check that FastAPI is running.');
    } finally {
      setBusy(false);
    }
  };

  const title = view === 'forgot' ? 'Reset your password' : view === 'reset' ? 'Choose a new password' : 'TrustScoreAI Login';
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-8 text-slate-800 shadow-md">
        <h2 className="mb-6 text-center text-2xl font-extrabold text-blue-900">{title}</h2>
        {error && <div role="alert" className="mb-4 rounded border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
        {message && <div role="status" className="mb-4 rounded border border-green-300 bg-green-50 px-4 py-3 text-sm text-green-800">{message}</div>}
        <form onSubmit={submit}>
          {view !== 'reset' && (
            <label className="mb-4 block text-sm font-bold">Email
              <input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)}
                className="mt-2 w-full rounded border border-slate-300 p-2 font-normal focus:ring-2 focus:ring-blue-500"
                placeholder="you@example.com" required />
            </label>
          )}
          {view === 'login' && (
            <label className="mb-2 block text-sm font-bold">Password
              <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)}
                className="mt-2 w-full rounded border border-slate-300 p-2 font-normal focus:ring-2 focus:ring-blue-500" required />
            </label>
          )}
          {view === 'forgot' && <p className="mb-4 text-sm text-slate-600">If the email belongs to an active account, reset instructions will be prepared.</p>}
          {view === 'reset' && (
            <>
              <p className="mb-4 text-sm text-slate-600">Use at least 12 characters with uppercase and lowercase letters, a number, and a symbol.</p>
              <label className="mb-4 block text-sm font-bold">New password
                <input type="password" autoComplete="new-password" minLength={12} value={newPassword} onChange={(e) => setNewPassword(e.target.value)}
                  className="mt-2 w-full rounded border border-slate-300 p-2 font-normal focus:ring-2 focus:ring-blue-500" required />
              </label>
              <label className="mb-5 block text-sm font-bold">Confirm new password
                <input type="password" autoComplete="new-password" minLength={12} value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
                  className="mt-2 w-full rounded border border-slate-300 p-2 font-normal focus:ring-2 focus:ring-blue-500" required />
              </label>
              {!resetToken && <p className="mb-3 text-sm text-red-700">This link has no reset token. Request a new link.</p>}
            </>
          )}
          <button type="submit" disabled={busy || (view === 'reset' && !resetToken)}
            className="w-full rounded bg-blue-700 py-2 font-bold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:bg-blue-400">
            {busy ? 'Please wait…' : view === 'login' ? 'Sign in' : view === 'forgot' ? 'Continue' : 'Update password'}
          </button>
        </form>
        <button type="button" onClick={() => changeView(view === 'login' ? 'forgot' : 'login')}
          className="mt-4 w-full text-sm font-semibold text-blue-700 hover:underline">
          {view === 'login' ? 'Forgot password?' : 'Back to sign in'}
        </button>
      </div>
    </div>
  );
}
