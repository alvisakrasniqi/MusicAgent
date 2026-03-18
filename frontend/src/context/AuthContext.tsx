import React, { createContext, useContext, useEffect, useState } from 'react';

import { api } from '../lib/api';

type AuthUser = {
  _id: string;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  spotify_connected: boolean;
};

type LoginPayload = {
  identifier: string;
  password: string;
};

type RegisterPayload = {
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  password: string;
};

type AuthContextValue = {
  user: AuthUser | null;
  isLoading: boolean;
  sessionError: string | null;
  login: (payload: LoginPayload) => Promise<AuthUser>;
  register: (payload: RegisterPayload) => Promise<AuthUser>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function getErrorStatus(error: unknown): number | undefined {
  if (typeof error !== 'object' || error === null || !('response' in error)) {
    return undefined;
  }

  const response = (error as { response?: { status?: number } }).response;
  return response?.status;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadSession() {
      try {
        const response = await api.get<AuthUser>('/api/auth/me');
        if (!isMounted) {
          return;
        }

        setUser(response.data);
        setSessionError(null);
      } catch (error) {
        if (!isMounted) {
          return;
        }

        setUser(null);

        if (getErrorStatus(error) === 401) {
          setSessionError(null);
        } else {
          setSessionError('Unable to restore your session. Make sure the backend is running.');
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadSession();

    return () => {
      isMounted = false;
    };
  }, []);

  async function login(payload: LoginPayload) {
    const response = await api.post<AuthUser>('/api/auth/login', payload);
    setUser(response.data);
    setSessionError(null);
    return response.data;
  }

  async function register(payload: RegisterPayload) {
    const response = await api.post<AuthUser>('/api/auth/register', payload);
    setUser(response.data);
    setSessionError(null);
    return response.data;
  }

  async function logout() {
    await api.post('/api/auth/logout');
    setUser(null);
    setSessionError(null);
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        sessionError,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }

  return context;
}
