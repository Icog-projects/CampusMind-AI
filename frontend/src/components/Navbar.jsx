import React from 'react';
import { useAuth } from '../context/AuthContext';

export const Navbar = ({ onNavigate }) => {
  const { user, isAuthenticated, logout } = useAuth();

  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo / Brand */}
          <div 
            className="flex items-center space-x-3 cursor-pointer group"
            onClick={() => onNavigate('home')}
          >
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20 group-hover:scale-105 transition-transform">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </div>
            <div>
              <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-700 to-indigo-800">
                CampusMind AI
              </span>
              <span className="hidden sm:inline-block ml-2 text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                Academic AI
              </span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="flex items-center space-x-2 sm:space-x-4">
            <button
              onClick={() => onNavigate('home')}
              className="text-sm font-medium text-slate-700 hover:text-blue-600 px-3 py-2 rounded-lg transition-colors"
            >
              Home
            </button>
            <a
              href="#how-it-works"
              className="text-sm font-medium text-slate-700 hover:text-blue-600 px-3 py-2 rounded-lg transition-colors hidden md:inline-block"
            >
              How It Works
            </a>
            <a
              href="#citations"
              className="text-sm font-medium text-slate-700 hover:text-blue-600 px-3 py-2 rounded-lg transition-colors hidden md:inline-block"
            >
              Citations & Evidence
            </a>

            {/* Auth Dependent Navigation */}
            {isAuthenticated ? (
              <div className="flex items-center space-x-3 pl-2 sm:pl-4 border-l border-slate-200">
                <button
                  onClick={() => onNavigate('chat')}
                  className="inline-flex items-center px-3.5 py-1.5 rounded-lg text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 shadow-sm transition-colors"
                >
                  <svg className="w-4 h-4 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                  AI Chat
                </button>

                <div className="hidden lg:flex flex-col text-right">
                  <span className="text-xs font-bold text-slate-800">{user?.name}</span>
                  <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">{user?.role}</span>
                </div>

                <button
                  onClick={logout}
                  className="text-sm font-medium text-slate-600 hover:text-red-600 px-3 py-1.5 rounded-lg border border-slate-200 hover:border-red-200 transition-colors"
                >
                  Sign Out
                </button>
              </div>
            ) : (
              <div className="flex items-center space-x-2 sm:space-x-3 pl-2 sm:pl-4 border-l border-slate-200">
                <button
                  onClick={() => onNavigate('login')}
                  className="text-sm font-semibold text-slate-700 hover:text-blue-700 px-3 py-2 rounded-lg transition-colors"
                >
                  Log In
                </button>
                <button
                  onClick={() => onNavigate('register')}
                  className="inline-flex items-center px-4 py-2 rounded-lg text-sm font-semibold text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 shadow-sm shadow-blue-500/20 transition-all hover:shadow"
                >
                  Get Started
                </button>
              </div>
            )}
          </nav>
        </div>
      </div>
    </header>
  );
};

