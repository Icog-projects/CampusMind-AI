import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { HomePage } from './components/HomePage';
import { AuthModal } from './components/AuthModal';

function MainApp() {
  const { isAuthenticated, user, loading } = useAuth();
  const [currentView, setCurrentView] = useState('home');
  const [authModal, setAuthModal] = useState({ isOpen: false, mode: 'login' });

  const handleNavigate = (view) => {
    if (view === 'login') {
      setAuthModal({ isOpen: true, mode: 'login' });
      return;
    }
    if (view === 'register') {
      setAuthModal({ isOpen: true, mode: 'register' });
      return;
    }
    if (view === 'chat') {
      if (!isAuthenticated) {
        setAuthModal({ isOpen: true, mode: 'login' });
        return;
      }
      setCurrentView('chat');
      return;
    }
    setCurrentView(view);
  };

  const handleAuthSuccess = (authenticatedUser) => {
    setAuthModal({ isOpen: false, mode: 'login' });
    // If admin logs in, remain on home or view appropriately with updated role
    setCurrentView('home');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="flex items-center space-x-3 text-slate-500 text-sm">
          <svg className="animate-spin h-5 w-5 text-blue-600" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span>Loading CampusMind AI...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 font-sans flex flex-col">
      <Navbar onNavigate={handleNavigate} />

      <main className="flex-1">
        {currentView === 'home' && <HomePage onNavigate={handleNavigate} />}

        {currentView === 'chat' && (
          <div className="max-w-4xl mx-auto px-4 py-16 text-center">
            <div className="p-8 bg-white rounded-2xl shadow-sm border border-slate-200">
              <div className="w-12 h-12 bg-blue-100 text-blue-700 rounded-xl flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <h2 className="text-2xl font-bold text-slate-900 mb-2">CampusMind AI Chat Interface</h2>
              <p className="text-slate-600 mb-6 text-sm">
                Authenticated session for <strong className="text-slate-800">{user?.name}</strong> ({user?.role}).
                The interactive chat workspace will be fully implemented in the upcoming chat stage.
              </p>
              <button
                onClick={() => setCurrentView('home')}
                className="px-5 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-sm font-semibold transition-colors"
              >
                &larr; Return to Home Page
              </button>
            </div>
          </div>
        )}
      </main>

      <AuthModal
        isOpen={authModal.isOpen}
        mode={authModal.mode}
        onClose={() => setAuthModal({ isOpen: false, mode: 'login' })}
        onSwitchMode={(mode) => setAuthModal({ isOpen: true, mode })}
        onSuccess={handleAuthSuccess}
      />
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <MainApp />
    </AuthProvider>
  );
}

export default App;
