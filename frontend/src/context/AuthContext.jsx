import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';

const AuthContext = createContext(null);

// In development, prefer relative path when proxy is available or fallback to explicit origin
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL !== undefined 
  ? import.meta.env.VITE_API_BASE_URL 
  : '';

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => localStorage.getItem('campusmind_token') || null);
  const [refreshToken, setRefreshToken] = useState(() => localStorage.getItem('campusmind_refresh_token') || null);
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('campusmind_user');
    try {
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(true);

  // Promise ref to deduplicate concurrent refresh requests
  const refreshPromiseRef = useRef(null);

  const logout = useCallback(async () => {
    const currentRefresh = localStorage.getItem('campusmind_refresh_token');
    const currentAccess = localStorage.getItem('campusmind_token');

    // Attempt backend revocation if token exists
    if (currentRefresh || currentAccess) {
      try {
        await fetch(`${API_BASE_URL}/auth/logout`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(currentAccess ? { 'Authorization': `Bearer ${currentAccess}` } : {}),
          },
          body: JSON.stringify({ refresh_token: currentRefresh || null }),
        });
      } catch (err) {
        console.warn('CampusMind Auth: Failed to revoke session during logout', err);
      }
    }

    setToken(null);
    setRefreshToken(null);
    setUser(null);
    localStorage.removeItem('campusmind_token');
    localStorage.removeItem('campusmind_refresh_token');
    localStorage.removeItem('campusmind_user');
  }, []);

  const login = useCallback((authToken, userData, rToken = null) => {
    setToken(authToken);
    setUser(userData);
    localStorage.setItem('campusmind_token', authToken);
    localStorage.setItem('campusmind_user', JSON.stringify(userData));
    if (rToken) {
      setRefreshToken(rToken);
      localStorage.setItem('campusmind_refresh_token', rToken);
    }
  }, []);

  /**
   * Refreshes the short-lived access token using the long-lived refresh token.
   * Concurrent calls share a single in-flight Promise to avoid racing refresh requests.
   */
  const refreshAccessToken = useCallback(async () => {
    if (refreshPromiseRef.current) {
      return refreshPromiseRef.current;
    }

    const currentRefreshToken = localStorage.getItem('campusmind_refresh_token');
    if (!currentRefreshToken) {
      logout();
      return null;
    }

    refreshPromiseRef.current = (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: currentRefreshToken }),
        });

        if (res.ok) {
          const data = await res.json();
          setToken(data.access_token);
          localStorage.setItem('campusmind_token', data.access_token);
          if (data.user) {
            setUser(data.user);
            localStorage.setItem('campusmind_user', JSON.stringify(data.user));
          }
          if (data.refresh_token) {
            setRefreshToken(data.refresh_token);
            localStorage.setItem('campusmind_refresh_token', data.refresh_token);
          }
          return data.access_token;
        } else {
          // Refresh token invalid, expired, or revoked
          logout();
          return null;
        }
      } catch (err) {
        console.warn('CampusMind Auth: Token refresh request failed', err);
        return null;
      } finally {
        refreshPromiseRef.current = null;
      }
    })();

    return refreshPromiseRef.current;
  }, [logout]);

  /**
   * Enhanced fetch client that automatically attaches Bearer access tokens,
   * catches 401 Unauthorized responses, renews the access token in background,
   * and retries the original request seamlessly.
   */
  const authFetch = useCallback(async (input, init = {}) => {
    const activeToken = localStorage.getItem('campusmind_token');
    const headers = new Headers(init.headers || {});

    if (activeToken && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${activeToken}`);
    }

    let response = await fetch(input, { ...init, headers });

    // If 401 Unauthorized, automatically attempt token renewal and retry once
    if (response.status === 401) {
      const currentRefresh = localStorage.getItem('campusmind_refresh_token');
      if (currentRefresh) {
        const newToken = await refreshAccessToken();
        if (newToken) {
          const retryHeaders = new Headers(init.headers || {});
          retryHeaders.set('Authorization', `Bearer ${newToken}`);
          response = await fetch(input, { ...init, headers: retryHeaders });
        }
      }
    }

    return response;
  }, [refreshAccessToken]);

  // Validate stored token against /auth/me on mount or token change, renewing if expired
  useEffect(() => {
    let isMounted = true;

    const validateToken = async () => {
      const storedToken = localStorage.getItem('campusmind_token');
      const storedRefresh = localStorage.getItem('campusmind_refresh_token');

      if (!storedToken && !storedRefresh) {
        if (isMounted) {
          setUser(null);
          setToken(null);
          setRefreshToken(null);
          setLoading(false);
        }
        return;
      }

      try {
        let activeToken = storedToken;
        let res = null;

        if (activeToken) {
          res = await fetch(`${API_BASE_URL}/auth/me`, {
            method: 'GET',
            headers: {
              'Authorization': `Bearer ${activeToken}`,
              'Content-Type': 'application/json',
            },
          });
        }

        // If access token is expired or missing but refresh token exists, attempt renewal
        if ((!res || res.status === 401) && storedRefresh) {
          activeToken = await refreshAccessToken();
          if (activeToken) {
            res = await fetch(`${API_BASE_URL}/auth/me`, {
              method: 'GET',
              headers: {
                'Authorization': `Bearer ${activeToken}`,
                'Content-Type': 'application/json',
              },
            });
          }
        }

        if (res && res.ok) {
          const userData = await res.json();
          if (isMounted) {
            setUser(userData);
            setToken(activeToken);
            localStorage.setItem('campusmind_user', JSON.stringify(userData));
          }
        } else if (res && (res.status === 401 || res.status === 403)) {
          if (isMounted) {
            logout();
          }
        }
      } catch (err) {
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
  }, [logout, refreshAccessToken]);

  const isAuthenticated = Boolean(token && user);

  return (
    <AuthContext.Provider value={{ 
      token, 
      refreshToken, 
      user, 
      isAuthenticated, 
      loading, 
      login, 
      logout, 
      refreshAccessToken, 
      authFetch, 
      API_BASE_URL 
    }}>
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
