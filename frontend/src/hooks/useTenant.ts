import { useState, useCallback } from 'react';

/**
 * Stub hook for tenant context.
 * Phase 3D will populate with real tenant switching logic.
 */
export default function useTenant() {
  const [activeTenantId, setActiveTenantId] = useState<string | null>(
    localStorage.getItem('aastreli_tenant_id')
  );

  const switchTenant = useCallback((tenantId: string) => {
    setActiveTenantId(tenantId);
    localStorage.setItem('aastreli_tenant_id', tenantId);
  }, []);

  return { activeTenantId, switchTenant };
}
