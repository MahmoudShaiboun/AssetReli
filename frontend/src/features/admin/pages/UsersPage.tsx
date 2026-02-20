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

interface User {
  id: string;
  tenant_id?: string;
  email?: string;
  username: string;
  full_name?: string;
  role: string;
  is_active: boolean;
  created_at?: string;
}

const EMPTY_FORM = {
  email: '',
  username: '',
  password: '',
  full_name: '',
  role: 'user',
  is_active: true,
  tenant_id: '',
};

export default function UsersPage() {
  const { tenantVersion, isSuperAdmin, tenants, tenantId } = useTenantContext();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null);
  // For super_admin: filter users by tenant
  const [filterTenantId, setFilterTenantId] = useState<string>('');

  const fetchUsers = async () => {
    try {
      const params: Record<string, string> = {};
      if (isSuperAdmin && filterTenantId) {
        params.tenant_id = filterTenantId;
      }
      const { data } = await apiClient.get('/users', { params });
      setUsers(Array.isArray(data) ? data : []);
    } catch (err: any) {
      console.error('Failed to load users:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [tenantVersion, filterTenantId]);

  const openCreateDialog = () => {
    setEditingId(null);
    setForm({ ...EMPTY_FORM, tenant_id: isSuperAdmin ? (filterTenantId || '') : '' });
    setError(null);
    setDialogOpen(true);
  };

  const openEditDialog = (user: User) => {
    setEditingId(user.id);
    setForm({
      email: user.email || '',
      username: user.username,
      password: '',
      full_name: user.full_name || '',
      role: user.role,
      is_active: user.is_active,
      tenant_id: user.tenant_id || '',
    });
    setError(null);
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    if (editingId) {
      setSubmitting(true);
      setError(null);
      try {
        const payload: Record<string, any> = {};
        if (form.full_name) payload.full_name = form.full_name;
        payload.role = form.role;
        payload.is_active = form.is_active;

        await apiClient.patch(`/users/${editingId}`, payload);
        setSuccess(`User "${form.username}" updated successfully`);
        setTimeout(() => setSuccess(null), 4000);
        setDialogOpen(false);
        setForm(EMPTY_FORM);
        setEditingId(null);
        await fetchUsers();
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to update user');
      } finally {
        setSubmitting(false);
      }
    } else {
      if (!form.email || !form.username || !form.password) {
        setError('Email, Username, and Password are required');
        return;
      }

      setSubmitting(true);
      setError(null);
      try {
        const payload: Record<string, any> = {
          email: form.email,
          username: form.username,
          password: form.password,
          role: form.role,
        };
        if (form.full_name) payload.full_name = form.full_name;
        // super_admin can assign user to a specific tenant
        if (isSuperAdmin && form.tenant_id) {
          payload.tenant_id = form.tenant_id;
        }

        await apiClient.post('/users', payload);
        setSuccess(`User "${form.username}" created successfully`);
        setTimeout(() => setSuccess(null), 4000);
        setDialogOpen(false);
        setForm(EMPTY_FORM);
        await fetchUsers();
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to create user');
      } finally {
        setSubmitting(false);
      }
    }
  };

  const handleToggleActive = async (user: User) => {
    try {
      await apiClient.patch(`/users/${user.id}`, {
        is_active: !user.is_active,
      });
      setSuccess(`User "${user.username}" ${user.is_active ? 'deactivated' : 'activated'} successfully`);
      setTimeout(() => setSuccess(null), 4000);
      await fetchUsers();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update user');
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;

    try {
      await apiClient.delete(`/users/${deleteTarget.id}`);
      setSuccess(`User "${deleteTarget.username}" deleted successfully`);
      setTimeout(() => setSuccess(null), 4000);
      setDeleteTarget(null);
      await fetchUsers();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete user');
      setDeleteTarget(null);
    }
  };

  // Role options based on current user's role
  const roleOptions = isSuperAdmin
    ? ['user', 'admin', 'super_admin']
    : ['user', 'admin'];

  // Helper to get tenant name by ID
  const getTenantName = (tid?: string) => {
    if (!tid) return '\u2014';
    const t = tenants.find((t) => t.id === tid);
    return t ? (t.tenant_name || t.tenant_code) : tid.slice(0, 8) + '...';
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
        <Typography variant="h4">Users</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreateDialog}>
          Add User
        </Button>
      </Box>

      {/* Super admin tenant filter */}
      {isSuperAdmin && tenants.length > 0 && (
        <Box sx={{ mb: 2 }}>
          <FormControl size="small" sx={{ minWidth: 250 }}>
            <InputLabel>Filter by Tenant</InputLabel>
            <Select
              value={filterTenantId}
              label="Filter by Tenant"
              onChange={(e) => { setFilterTenantId(e.target.value); setLoading(true); }}
            >
              <MenuItem value="">All Tenants</MenuItem>
              {tenants.map((t) => (
                <MenuItem key={t.id} value={t.id}>
                  {t.tenant_name || t.tenant_code}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>
      )}

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
              <TableCell><strong>Username</strong></TableCell>
              <TableCell><strong>Email</strong></TableCell>
              <TableCell><strong>Full Name</strong></TableCell>
              {isSuperAdmin && <TableCell><strong>Tenant</strong></TableCell>}
              <TableCell><strong>Role</strong></TableCell>
              <TableCell><strong>Status</strong></TableCell>
              <TableCell><strong>Created</strong></TableCell>
              <TableCell align="right"><strong>Actions</strong></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {users.length === 0 ? (
              <TableRow>
                <TableCell colSpan={isSuperAdmin ? 8 : 7} align="center">
                  <Typography variant="body2" color="text.secondary" sx={{ py: 4 }}>
                    No users found. Click "Add User" to create one.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              users.map((user) => (
                <TableRow key={user.id} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                      {user.username}
                    </Typography>
                  </TableCell>
                  <TableCell>{user.email || '\u2014'}</TableCell>
                  <TableCell>{user.full_name || '\u2014'}</TableCell>
                  {isSuperAdmin && (
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {getTenantName(user.tenant_id)}
                      </Typography>
                    </TableCell>
                  )}
                  <TableCell>
                    <Chip
                      label={user.role}
                      size="small"
                      color={
                        user.role === 'super_admin'
                          ? 'warning'
                          : user.role === 'admin'
                          ? 'primary'
                          : 'default'
                      }
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={user.is_active ? 'Active' : 'Inactive'}
                      size="small"
                      color={user.is_active ? 'success' : 'default'}
                      onClick={() => handleToggleActive(user)}
                      sx={{ cursor: 'pointer' }}
                    />
                  </TableCell>
                  <TableCell>
                    {user.created_at
                      ? new Date(user.created_at).toLocaleDateString()
                      : '\u2014'}
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="Edit">
                      <IconButton size="small" onClick={() => openEditDialog(user)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton size="small" color="error" onClick={() => setDeleteTarget(user)}>
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
        <DialogTitle>{editingId ? 'Edit User' : 'Create User'}</DialogTitle>
        <DialogContent>
          {error && dialogOpen && (
            <Alert severity="error" sx={{ mb: 2, mt: 1 }} onClose={() => setError(null)}>{error}</Alert>
          )}
          {!editingId && (
            <>
              <TextField
                fullWidth required label="Email" type="email" value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                sx={{ mt: 2, mb: 2 }} placeholder="e.g. user@example.com"
              />
              <TextField
                fullWidth required label="Username" value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                sx={{ mb: 2 }} placeholder="e.g. jsmith"
              />
              <TextField
                fullWidth required label="Password" type="password" value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                sx={{ mb: 2 }}
              />
            </>
          )}
          <TextField
            fullWidth label="Full Name" value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            sx={{ mt: editingId ? 2 : 0, mb: 2 }} placeholder="e.g. John Smith"
          />
          {/* Super admin can assign user to a tenant when creating */}
          {isSuperAdmin && !editingId && tenants.length > 0 && (
            <FormControl fullWidth sx={{ mb: 2 }}>
              <InputLabel>Tenant</InputLabel>
              <Select
                value={form.tenant_id}
                label="Tenant"
                onChange={(e) => setForm({ ...form, tenant_id: e.target.value })}
              >
                <MenuItem value="">
                  <em>None (platform-level)</em>
                </MenuItem>
                {tenants.map((t) => (
                  <MenuItem key={t.id} value={t.id}>
                    {t.tenant_name || t.tenant_code}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Role</InputLabel>
            <Select
              value={form.role}
              label="Role"
              onChange={(e) => setForm({ ...form, role: e.target.value })}
            >
              {roleOptions.map((r) => (
                <MenuItem key={r} value={r}>
                  {r === 'super_admin' ? 'Super Admin' : r.charAt(0).toUpperCase() + r.slice(1)}
                </MenuItem>
              ))}
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
            disabled={submitting || (!editingId && (!form.email || !form.username || !form.password))}
          >
            {submitting ? 'Saving...' : editingId ? 'Update User' : 'Create User'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirm Dialog */}
      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete User"
        message={`Are you sure you want to delete user "${deleteTarget?.username}"? This action cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </Container>
  );
}
