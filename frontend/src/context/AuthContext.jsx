import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const AuthContext = createContext(null);

// In development, prefer relative path when proxy is available or fallback to explicit origin
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL !== undefined 
  ? import.meta.env.VITE_API_BASE_URL 
  : '';

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

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('campusmind_token');
    localStorage.removeItem('campusmind_user');
  }, []);

  const login = useCallback((authToken, userData) => {
    setToken(authToken);
    setUser(userData);
    localStorage.setItem('campusmind_token', authToken);
    localStorage.setItem('campusmind_user', JSON.stringify(userData));
  }, []);

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
        const url = `${API_BASE_URL}/auth/me`;
        const res = await fetch(url, {
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
        } else if (res.status === 401 || res.status === 403) {
          // Token is definitively invalid, expired, or rejected
          if (isMounted) {
            logout();
          }
        }
      } catch (err) {
        // Network blip; don't forcefully logout if cached session is still readable
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
  }, [logout]);

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
