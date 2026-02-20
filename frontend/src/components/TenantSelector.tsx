import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  Box,
  CircularProgress,
} from '@mui/material';
import { useTenantContext } from '../contexts/TenantContext';

/**
 * Overlay dialog shown when a super_admin has not yet selected a tenant.
 * Prevents navigation to tenant-scoped pages without a tenant context.
 */
export default function TenantSelector() {
  const { isSuperAdmin, tenantId, tenants, isLoading, switchTenant } = useTenantContext();
  const [selected, setSelected] = React.useState('');

  // Only show for super_admin who hasn't selected a tenant
  if (!isSuperAdmin || tenantId || isLoading) return null;

  // If tenants haven't loaded yet, show spinner
  if (tenants.length === 0) {
    return (
      <Dialog open maxWidth="xs" fullWidth>
        <DialogContent sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open maxWidth="xs" fullWidth disableEscapeKeyDown>
      <DialogTitle>Select a Tenant</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          As a platform administrator, you must select a tenant context before viewing tenant data.
        </Typography>
        <FormControl fullWidth sx={{ mt: 1 }}>
          <InputLabel>Tenant</InputLabel>
          <Select
            value={selected}
            label="Tenant"
            onChange={(e) => setSelected(e.target.value)}
          >
            {tenants.map((t) => (
              <MenuItem key={t.id} value={t.id}>
                {t.tenant_name || t.tenant_code}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button
          variant="contained"
          disabled={!selected}
          onClick={() => switchTenant(selected)}
        >
          Continue
        </Button>
      </DialogActions>
    </Dialog>
  );
}
