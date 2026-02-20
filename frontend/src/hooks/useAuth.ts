import { useState, useEffect, useCallback } from 'react';
import authService from '../api/auth';

export default function useAuth() {
  const [user, setUser] = useState(authService.getCurrentUser());
  const [isAuthenticated, setIsAuthenticated] = useState(authService.isAuthenticated());

  useEffect(() => {
    setUser(authService.getCurrentUser());
    setIsAuthenticated(authService.isAuthenticated());
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const result = await authService.login(email, password);
    setUser(authService.getCurrentUser());
    setIsAuthenticated(true);
    return result;
  }, []);

  const logout = useCallback(() => {
    authService.logout();
    setUser(null);
    setIsAuthenticated(false);
  }, []);

  return { user, isAuthenticated, login, logout };
}
