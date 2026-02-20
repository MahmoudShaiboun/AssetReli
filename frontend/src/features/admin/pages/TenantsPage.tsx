import React, { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Paper,
  Box,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  CircularProgress,
  IconButton,
  Tooltip,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Switch,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import apiClient from '../../../api/client';
import ConfirmDialog from '../../../components/ConfirmDialog';
import { useTenantContext } from '../../../contexts/TenantContext';

interface Tenant {
  id: string;
  tenant_code: string;
  tenant_name: string;
  plan: string;
  is_active: boolean;
  created_at?: string;
}

const EMPTY_FORM = {
  tenant_code: '',
  tenant_name: '',
  plan: 'free',
  is_active: true,
};

export default function TenantsPage() {
  const { tenantVersion } = useTenantContext();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Tenant | null>(null);

  const fetchTenants = async () => {
    try {
      const { data } = await apiClient.get('/tenants');
      setTenants(Array.isArray(data) ? data : []);
    } catch (err: any) {
      console.error('Failed to load tenants:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTenants();
  }, [tenantVersion]);

  const openCreateDialog = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setError(null);
    setDialogOpen(true);
  };

  const openEditDialog = (tenant: Tenant) => {
    setEditingId(tenant.id);
    setForm({
      tenant_code: tenant.tenant_code,
      tenant_name: tenant.tenant_name,
      plan: tenant.plan,
      is_active: tenant.is_active,
    });
    setError(null);
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    if (!form.tenant_code || !form.tenant_name) {
      setError('Tenant Code and Tenant Name are required');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      if (editingId) {
        await apiClient.patch(`/tenants/${editingId}`, {
          tenant_name: form.tenant_name,
          plan: form.plan,
          is_active: form.is_active,
        });
        setSuccess(`Tenant "${form.tenant_code}" updated successfully`);
      } else {
        await apiClient.post('/tenants', {
          tenant_code: form.tenant_code,
          tenant_name: form.tenant_name,
          plan: form.plan,
        });
        setSuccess(`Tenant "${form.tenant_code}" created successfully`);
      }

      setTimeout(() => setSuccess(null), 4000);
      setDialogOpen(false);
      setForm(EMPTY_FORM);
      setEditingId(null);
      await fetchTenants();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save tenant');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleActive = async (tenant: Tenant) => {
    try {
      await apiClient.patch(`/tenants/${tenant.id}`, {
        is_active: !tenant.is_active,
      });
      setSuccess(`Tenant "${tenant.tenant_code}" ${tenant.is_active ? 'deactivated' : 'activated'} successfully`);
      setTimeout(() => setSuccess(null), 4000);
      await fetchTenants();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update tenant');
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;

    try {
      await apiClient.delete(`/tenants/${deleteTarget.id}`);
      setSuccess(`Tenant "${deleteTarget.tenant_code}" deleted successfully`);
      setTimeout(() => setSuccess(null), 4000);
      setDeleteTarget(null);
      await fetchTenants();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete tenant');
      setDeleteTarget(null);
    }
  };

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress />
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Tenants</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreateDialog}>
          Add Tenant
        </Button>
      </Box>

      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>{success}</Alert>
      )}
      {error && !dialogOpen && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>
      )}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell><strong>Tenant Code</strong></TableCell>
              <TableCell><strong>Tenant Name</strong></TableCell>
              <TableCell><strong>Plan</strong></TableCell>
              <TableCell><strong>Status</strong></TableCell>
              <TableCell><strong>Created</strong></TableCell>
              <TableCell align="right"><strong>Actions</strong></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {tenants.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  <Typography variant="body2" color="text.secondary" sx={{ py: 4 }}>
                    No tenants found. Click "Add Tenant" to create one.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              tenants.map((tenant) => (
                <TableRow key={tenant.id} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                      {tenant.tenant_code}
                    </Typography>
                  </TableCell>
                  <TableCell>{tenant.tenant_name}</TableCell>
                  <TableCell>
                    <Chip label={tenant.plan} size="small" variant="outlined" />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={tenant.is_active ? 'Active' : 'Inactive'}
                      size="small"
                      color={tenant.is_active ? 'success' : 'default'}
                      onClick={() => handleToggleActive(tenant)}
                      sx={{ cursor: 'pointer' }}
                    />
                  </TableCell>
                  <TableCell>
                    {tenant.created_at
                      ? new Date(tenant.created_at).toLocaleDateString()
                      : '\u2014'}
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="Edit">
                      <IconButton size="small" onClick={() => openEditDialog(tenant)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton size="small" color="error" onClick={() => setDeleteTarget(tenant)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingId ? 'Edit Tenant' : 'Create Tenant'}</DialogTitle>
        <DialogContent>
          {error && dialogOpen && (
            <Alert severity="error" sx={{ mb: 2, mt: 1 }} onClose={() => setError(null)}>{error}</Alert>
          )}
          <TextField
            fullWidth required label="Tenant Code" value={form.tenant_code}
            onChange={(e) => setForm({ ...form, tenant_code: e.target.value })}
            sx={{ mt: 2, mb: 2 }} placeholder="e.g. acme-corp"
            disabled={!!editingId}
            helperText={editingId ? 'Tenant code cannot be changed' : ''}
          />
          <TextField
            fullWidth required label="Tenant Name" value={form.tenant_name}
            onChange={(e) => setForm({ ...form, tenant_name: e.target.value })}
            sx={{ mb: 2 }} placeholder="e.g. Acme Corporation"
          />
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Plan</InputLabel>
            <Select
              value={form.plan}
              label="Plan"
              onChange={(e) => setForm({ ...form, plan: e.target.value })}
            >
              <MenuItem value="free">Free</MenuItem>
              <MenuItem value="pro">Pro</MenuItem>
              <MenuItem value="enterprise">Enterprise</MenuItem>
            </Select>
          </FormControl>
          {editingId && (
            <FormControlLabel
              control={
                <Switch
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                />
              }
              label="Active"
            />
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => { setDialogOpen(false); setError(null); }}>Cancel</Button>
          <Button
            variant="contained" onClick={handleSubmit}
            disabled={submitting || !form.tenant_code || !form.tenant_name}
          >
            {submitting ? 'Saving...' : editingId ? 'Update Tenant' : 'Create Tenant'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirm Dialog */}
      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Tenant"
        message={`Are you sure you want to delete tenant "${deleteTarget?.tenant_code}"? This action cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </Container>
  );
}
