import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

export const AuthModal = ({ mode, isOpen, onClose, onSwitchMode, onSuccess }) => {
  const { login, API_BASE_URL } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const isLogin = mode === 'login';

  const resetForm = () => {
    setEmail('');
    setPassword('');
    setName('');
    setError(null);
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  const handleSwitch = (newMode) => {
    resetForm();
    onSwitchMode(newMode);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    const cleanEmail = email.trim();
    if (!cleanEmail) {
      setError('Please provide a valid university email address.');
      return;
    }
    if (!password || password.length < 6) {
      setError('Password must be at least 6 characters long.');
      return;
    }

    setLoading(true);

    try {
      if (isLogin) {
        // Authenticate user
        const res = await fetch(`${API_BASE_URL}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: cleanEmail, password }),
        });

        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || 'Invalid email or password.');
        }

        login(data.access_token, data.user);
        resetForm();
        onSuccess();
      } else {
        // Registration flow - strictly creates student account
        const cleanName = name.trim();
        if (!cleanName) {
          throw new Error('Please enter your full name.');
        }

        const res = await fetch(`${API_BASE_URL}/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: cleanName,
            email: cleanEmail,
            password,
            role: 'student', // Strict student default per SRS v1.2
          }),
        });

        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || 'Registration failed. Please check your details.');
        }

        // Automatic seamless login following successful registration
        const loginRes = await fetch(`${API_BASE_URL}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: cleanEmail, password }),
        });
        const loginData = await loginRes.json();
        if (loginRes.ok) {
          login(loginData.access_token, loginData.user);
          resetForm();
          onSuccess();
        } else {
          // If auto-login fails, redirect user to login tab with clear message
          handleSwitch('login');
        }
      }
    } catch (err) {
      setError(err.message || 'An unexpected error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl border border-slate-100 p-6 sm:p-8">
        {/* Close Button */}
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 p-1 rounded-lg transition-colors"
          aria-label="Close"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Modal Title */}
        <div className="text-center mb-6">
          <div className="inline-flex w-12 h-12 rounded-xl bg-blue-50 text-blue-600 items-center justify-center mb-3">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </div>
          <h3 className="text-2xl font-bold text-slate-900">
            {isLogin ? 'Sign In to CampusMind' : 'Create Student Account'}
          </h3>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            {isLogin
              ? 'Access verified university RAG Q&A'
              : 'Register as a student to start asking grounded academic questions'}
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs flex items-start space-x-2">
            <svg className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {!isLogin && (
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                Full Name
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Jane Doe"
                disabled={loading}
                className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-600/20 focus:border-blue-600 disabled:bg-slate-50 disabled:text-slate-500"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
              University Email
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@campus.edu"
              disabled={loading}
              className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-600/20 focus:border-blue-600 disabled:bg-slate-50 disabled:text-slate-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              disabled={loading}
              className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-600/20 focus:border-blue-600 disabled:bg-slate-50 disabled:text-slate-500"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 px-4 rounded-xl text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 shadow-md shadow-blue-500/20 transition-all disabled:opacity-50 flex items-center justify-center space-x-2"
          >
            {loading && (
              <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            )}
            <span>{loading ? 'Processing...' : isLogin ? 'Sign In' : 'Create Student Account'}</span>
          </button>
        </form>

        <div className="mt-6 text-center text-xs text-slate-600">
          {isLogin ? (
            <span>
              Don't have an account?{' '}
              <button
                type="button"
                onClick={() => handleSwitch('register')}
                className="font-semibold text-blue-600 hover:underline"
              >
                Register
              </button>
            </span>
          ) : (
            <span>
              Already registered?{' '}
              <button
                type="button"
                onClick={() => handleSwitch('login')}
                className="font-semibold text-blue-600 hover:underline"
              >
                Sign In
              </button>
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
