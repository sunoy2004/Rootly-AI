import React, { createContext, useContext, useState, useCallback } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);

const INCIDENT_API = import.meta.env.VITE_API_URL || '/api';

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null);

  const login = useCallback(async (username, password) => {
    const response = await axios.post(`${INCIDENT_API}/auth/login`, {
      username,
      password,
    });
    const { access_token } = response.data;
    setToken(access_token);
    return access_token;
  }, []);

  const logout = useCallback(() => {
    setToken(null);
  }, []);

  const isAuthenticated = !!token;

  const getAuthHeader = useCallback(() => {
    if (!token) return {};
    return { Authorization: `Bearer ${token}` };
  }, [token]);

  return (
    <AuthContext.Provider
      value={{
        token,
        login,
        logout,
        isAuthenticated,
        getAuthHeader,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
