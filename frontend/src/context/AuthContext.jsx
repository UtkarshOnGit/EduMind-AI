import React, { createContext, useContext, useState, useEffect } from 'react';
import api from '../services/api';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('edumind_token') || null);
  const [loading, setLoading] = useState(true);

  // Initialize auth state from local storage or verify with /me
  useEffect(() => {
    const initAuth = async () => {
      const savedToken = localStorage.getItem('edumind_token');
      const savedUser = localStorage.getItem('edumind_user');

      if (savedToken && savedUser) {
        setUser(JSON.parse(savedUser));
        setToken(savedToken);
        try {
          const res = await api.get('/auth/me');
          if (res.data.success) {
            setUser(res.data.data);
            localStorage.setItem('edumind_user', JSON.stringify(res.data.data));
          }
        } catch (err) {
          console.warn('Session expired or invalid token', err);
          logout();
        }
      }
      setLoading(false);
    };

    initAuth();
  }, []);

  const login = async (email, password) => {
    const res = await api.post('/auth/login', { email, password });
    if (res.data.success) {
      const { token, ...userData } = res.data.data;
      localStorage.setItem('edumind_token', token);
      localStorage.setItem('edumind_user', JSON.stringify(userData));
      setToken(token);
      setUser(userData);
      return userData;
    }
  };

  const register = async (name, email, password, role) => {
    const res = await api.post('/auth/register', { name, email, password, role });
    if (res.data.success) {
      const { token, ...userData } = res.data.data;
      localStorage.setItem('edumind_token', token);
      localStorage.setItem('edumind_user', JSON.stringify(userData));
      setToken(token);
      setUser(userData);
      return userData;
    }
  };

  const logout = () => {
    localStorage.removeItem('edumind_token');
    localStorage.removeItem('edumind_user');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        register,
        logout,
        isAuthenticated: !!token,
        isProfessor: user?.role === 'professor',
        isStudent: user?.role === 'student'
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
