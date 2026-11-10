import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { HomePage } from './components/HomePage';
import { AdminDashboard } from './components/AdminDashboard';
import { DocumentManagement } from './components/DocumentManagement';
import { CacheAnalytics } from './components/CacheAnalytics';
import { ChatPage } from './components/ChatPage';
import { AuthModal } from './components/AuthModal';

function MainApp() {
  const { isAuthenticated, user, loading } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [currentView, setCurrentView] = useState(() => (isAdmin ? 'dashboard' : 'home'));
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

    // Role-based route guard for administrative pages (SRS v1.2 Section 3.1)
    const adminViews = ['dashboard', 'documents', 'cache-analytics'];
    if (adminViews.includes(view)) {
      if (!isAuthenticated) {
        setAuthModal({ isOpen: true, mode: 'login' });
        return;
      }
      if (!isAdmin) {
        // Students/staff are not authorized to view admin pages
        setCurrentView('home');
        return;
      }
    }

    setCurrentView(view);
  };

  const handleAuthSuccess = (authenticatedUser) => {
    setAuthModal({ isOpen: false, mode: 'login' });
    // Per SRS v1.2 Section 3.1: Admins are directed to Admin Dashboard by default; students to AI Chat
    if (authenticatedUser?.role === 'admin') {
      setCurrentView('dashboard');
    } else {
      setCurrentView('chat');
    }
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
      <Navbar currentView={currentView} onNavigate={handleNavigate} />

      <main className="flex-1">
        {/* Public Home Page */}
        {currentView === 'home' && <HomePage onNavigate={handleNavigate} />}

        {/* Functional AI Chat Interface (SRS v1.2 Section 3, FR-05, FR-06, FR-19) */}
        {currentView === 'chat' && (
          isAuthenticated ? (
            <ChatPage onNavigate={handleNavigate} />
          ) : (
            <div className="max-w-md mx-auto my-16 p-6 bg-white rounded-2xl border border-slate-200 text-center">
              <h2 className="text-lg font-bold text-slate-900">Authentication Required</h2>
              <p className="text-xs text-slate-600 mt-2">Please sign in to access the verified academic chat assistant.</p>
              <button
                onClick={() => handleNavigate('login')}
                className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-sm"
              >
                Sign In
              </button>
            </div>
          )
        )}

        {/* Admin Dashboard */}
        {currentView === 'dashboard' && (
          isAdmin ? (
            <AdminDashboard onNavigate={handleNavigate} />
          ) : (
            <div className="max-w-md mx-auto my-16 p-6 bg-white rounded-2xl border border-red-200 text-center">
              <h2 className="text-lg font-bold text-red-700">Access Restricted</h2>
              <p className="text-xs text-slate-600 mt-2">Administrator privileges required to access the dashboard.</p>
              <button
                onClick={() => setCurrentView('home')}
                className="mt-4 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg"
              >
                Return to Home
              </button>
            </div>
          )
        )}

        {/* Document Management */}
        {currentView === 'documents' && (
          isAdmin ? (
            <DocumentManagement onNavigate={handleNavigate} />
          ) : (
            <div className="max-w-md mx-auto my-16 p-6 bg-white rounded-2xl border border-red-200 text-center">
              <h2 className="text-lg font-bold text-red-700">Access Restricted</h2>
              <p className="text-xs text-slate-600 mt-2">Administrator privileges required to manage documents.</p>
              <button
                onClick={() => setCurrentView('home')}
                className="mt-4 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg"
              >
                Return to Home
              </button>
            </div>
          )
        )}

        {/* Redis Cache Analytics */}
        {currentView === 'cache-analytics' && (
          isAdmin ? (
            <CacheAnalytics onNavigate={handleNavigate} />
          ) : (
            <div className="max-w-md mx-auto my-16 p-6 bg-white rounded-2xl border border-red-200 text-center">
              <h2 className="text-lg font-bold text-red-700">Access Restricted</h2>
              <p className="text-xs text-slate-600 mt-2">Administrator privileges required to view cache telemetry.</p>
              <button
                onClick={() => setCurrentView('home')}
                className="mt-4 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg"
              >
                Return to Home
              </button>
            </div>
          )
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
