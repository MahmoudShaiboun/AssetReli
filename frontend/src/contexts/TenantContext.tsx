import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import apiClient from '../api/client';
import authService from '../api/auth';

interface Tenant {
  id: string;
  tenant_code: string;
  tenant_name: string;
  is_active: boolean;
}

interface TenantContextValue {
  tenantId: string | null;
  tenantCode: string | null;
  tenants: Tenant[];
  isLoading: boolean;
  isSuperAdmin: boolean;
  isAdmin: boolean;
  scope: 'platform' | 'tenant';
  /** Increments on every tenant switch — use as useEffect dependency to re-fetch data */
  tenantVersion: number;
  switchTenant: (tenantId: string) => void;
  /** Re-read JWT and reset all tenant/role state. Call after login or logout. */
  refreshFromToken: () => void;
}

const TenantContext = createContext<TenantContextValue>({
  tenantId: null,
  tenantCode: null,
  tenants: [],
  isLoading: false,
  isSuperAdmin: false,
  isAdmin: false,
  scope: 'tenant',
  tenantVersion: 0,
  switchTenant: () => {},
  refreshFromToken: () => {},
});

export function useTenantContext() {
  return useContext(TenantContext);
}

function decodeJwtPayload(token: string): Record<string, any> | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    return payload;
  } catch {
    return null;
  }
}

export function TenantProvider({ children }: { children: React.ReactNode }) {
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [tenantCode, setTenantCode] = useState<string | null>(null);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [scope, setScope] = useState<'platform' | 'tenant'>('tenant');
  const [tenantVersion, setTenantVersion] = useState(0);

  // Core logic to read JWT and reset all tenant/role state
  const initFromToken = useCallback(() => {
    const token = authService.getToken();
    if (!token) {
      // No token (logged out) — reset everything
      setTenantId(null);
      setTenantCode(null);
      setTenants([]);
      setIsSuperAdmin(false);
      setIsAdmin(false);
      setScope('tenant');
      return;
    }

    const payload = decodeJwtPayload(token);
    if (!payload) return;

    const jwtTenantId = payload.tenant_id || null;
    const jwtTenantCode = payload.tenant_code || null;
    const role = payload.role || '';
    const jwtScope = payload.scope || 'tenant';

    setScope(jwtScope as 'platform' | 'tenant');
    setIsSuperAdmin(role === 'super_admin');
    setIsAdmin(role === 'admin');

    if (jwtScope === 'platform') {
      // Platform-scoped (super_admin): load tenant list, use stored override if any
      const overrideId = localStorage.getItem('aastreli_tenant_id');
      setTenantId(overrideId || null);
      setTenantCode(null);
      setIsLoading(true);
      apiClient
        .get('/tenants')
        .then((res) => {
          const data = Array.isArray(res.data) ? res.data : [];
          setTenants(data);
          if (overrideId) {
            const match = data.find((t: Tenant) => t.id === overrideId);
            if (match) setTenantCode(match.tenant_code);
          }
        })
        .catch(() => {})
        .finally(() => setIsLoading(false));
    } else {
      // Tenant-scoped: use JWT tenant_id, clear platform state
      setTenantId(jwtTenantId);
      setTenantCode(jwtTenantCode);
      setTenants([]);
    }
  }, []);

  // Decode JWT on initial mount
  useEffect(() => {
    initFromToken();
  }, [initFromToken]);

  const switchTenant = useCallback(
    (newTenantId: string) => {
      setTenantId(newTenantId);
      localStorage.setItem('aastreli_tenant_id', newTenantId);
      // Update tenant_code from the tenants list
      const match = tenants.find((t) => t.id === newTenantId);
      if (match) setTenantCode(match.tenant_code);
      // Bump version so pages re-fetch data
      setTenantVersion((v) => v + 1);
    },
    [tenants],
  );

  return (
    <TenantContext.Provider
      value={{
        tenantId, tenantCode, tenants, isLoading,
        isSuperAdmin, isAdmin, scope, tenantVersion, switchTenant,
        refreshFromToken: initFromToken,
      }}
    >
      {children}
    </TenantContext.Provider>
  );
}

export default TenantContext;
