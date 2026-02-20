import React from 'react';
import { Navigate } from 'react-router-dom';
import authService from '../api/auth';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRoles?: string[];
}

function decodeTokenPayload(token: string): Record<string, any> | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    return JSON.parse(atob(parts[1]));
  } catch {
    return null;
  }
}

function isTokenExpired(token: string): boolean {
  const payload = decodeTokenPayload(token);
  if (!payload || !payload.exp) return false;
  return Date.now() >= payload.exp * 1000;
}

export default function ProtectedRoute({ children, requiredRoles }: ProtectedRouteProps) {
  const token = authService.getToken();

  if (!token || isTokenExpired(token)) {
    authService.logout();
    return <Navigate to="/login" replace />;
  }

  // Role-based route guard
  if (requiredRoles && requiredRoles.length > 0) {
    const payload = decodeTokenPayload(token);
    const role = payload?.role || '';
    // super_admin passes all role checks
    if (role !== 'super_admin' && !requiredRoles.includes(role)) {
      return <Navigate to="/" replace />;
    }
  }

  return <>{children}</>;
}
