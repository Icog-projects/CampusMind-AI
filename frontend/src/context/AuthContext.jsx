import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => localStorage.getItem('campusmind_token') || null);
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('campusmind_user');
    try {
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(true);

  // Validate stored token against /auth/me on mount or token change
  useEffect(() => {
    let isMounted = true;

    const validateToken = async () => {
      const storedToken = localStorage.getItem('campusmind_token');
      if (!storedToken) {
        if (isMounted) {
          setUser(null);
          setToken(null);
          setLoading(false);
        }
        return;
      }

      try {
        const res = await fetch(`${API_BASE_URL}/auth/me`, {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${storedToken}`,
            'Content-Type': 'application/json',
          },
        });

        if (res.ok) {
          const userData = await res.json();
          if (isMounted) {
            setUser(userData);
            setToken(storedToken);
            localStorage.setItem('campusmind_user', JSON.stringify(userData));
          }
        } else {
          // Token is invalid, expired, or user was deleted
          if (isMounted) {
            logout();
          }
        }
      } catch (err) {
        // If backend is momentarily unreachable on page reload, retain existing cached user or logout gracefully
        console.warn('CampusMind Auth: Token validation network error', err);
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    validateToken();

    return () => {
      isMounted = false;
    };
  }, []);

  const login = (authToken, userData) => {
    setToken(authToken);
    setUser(userData);
    localStorage.setItem('campusmind_token', authToken);
    localStorage.setItem('campusmind_user', JSON.stringify(userData));
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('campusmind_token');
    localStorage.removeItem('campusmind_user');
  };

  const isAuthenticated = Boolean(token && user);

  return (
    <AuthContext.Provider value={{ token, user, isAuthenticated, loading, login, logout, API_BASE_URL }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
