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
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  IconButton,
  Tooltip,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import apiClient from '../../../api/client';
import ConfirmDialog from '../../../components/ConfirmDialog';
import { useTenantContext } from '../../../contexts/TenantContext';

interface Site {
  id: string;
  site_code: string;
  site_name: string;
}

interface Gateway {
  id: string;
  gateway_code: string;
  site_id: string;
  ip_address?: string;
  firmware_version?: string;
}

const EMPTY_FORM = {
  gateway_code: '',
  site_id: '',
  ip_address: '',
  firmware_version: '',
};

export default function GatewaysPage() {
  const { tenantVersion } = useTenantContext();
  const [gateways, setGateways] = useState<Gateway[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Gateway | null>(null);

  const fetchSites = async () => {
    try {
      const { data } = await apiClient.get('/sites');
      setSites(Array.isArray(data) ? data : data.sites || []);
    } catch (err: any) {
      console.error('Failed to load sites:', err);
    }
  };

  const fetchGateways = async () => {
    try {
      const { data } = await apiClient.get('/gateways');
      setGateways(Array.isArray(data) ? data : data.gateways || []);
    } catch (err: any) {
      console.error('Failed to load gateways:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSites();
    fetchGateways();
  }, [tenantVersion]);

  const getSiteName = (siteId: string): string => {
    const site = sites.find((s) => s.id === siteId);
    return site ? `${site.site_name} (${site.site_code})` : siteId;
  };

  const openCreateDialog = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setError(null);
    setDialogOpen(true);
  };

  const openEditDialog = (gw: Gateway) => {
    setEditingId(gw.id);
    setForm({
      gateway_code: gw.gateway_code,
      site_id: gw.site_id,
      ip_address: gw.ip_address || '',
      firmware_version: gw.firmware_version || '',
    });
    setError(null);
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    if (!form.gateway_code || !form.site_id) {
      setError('Gateway Code and Site are required');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const payload: Record<string, string> = {
        gateway_code: form.gateway_code,
        site_id: form.site_id,
      };
      if (form.ip_address) payload.ip_address = form.ip_address;
      if (form.firmware_version) payload.firmware_version = form.firmware_version;

      if (editingId) {
        await apiClient.patch(`/gateways/${editingId}`, payload);
        setSuccess(`Gateway "${form.gateway_code}" updated successfully`);
      } else {
        await apiClient.post('/gateways', payload);
        setSuccess(`Gateway "${form.gateway_code}" created successfully`);
      }

      setTimeout(() => setSuccess(null), 4000);
      setDialogOpen(false);
      setForm(EMPTY_FORM);
      setEditingId(null);
      await fetchGateways();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save gateway');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;

    try {
      await apiClient.delete(`/gateways/${deleteTarget.id}`);
      setSuccess(`Gateway "${deleteTarget.gateway_code}" deleted successfully`);
      setTimeout(() => setSuccess(null), 4000);
      setDeleteTarget(null);
      await fetchGateways();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete gateway');
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
        <Typography variant="h4">Gateways</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreateDialog}>
          Add Gateway
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
              <TableCell><strong>Gateway Code</strong></TableCell>
              <TableCell><strong>Site</strong></TableCell>
              <TableCell><strong>IP Address</strong></TableCell>
              <TableCell><strong>Firmware</strong></TableCell>
              <TableCell align="right"><strong>Actions</strong></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {gateways.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} align="center">
                  <Typography variant="body2" color="text.secondary" sx={{ py: 4 }}>
                    No gateways configured. Click "Add Gateway" to get started.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              gateways.map((gw) => (
                <TableRow key={gw.id} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                      {gw.gateway_code}
                    </Typography>
                  </TableCell>
                  <TableCell>{getSiteName(gw.site_id)}</TableCell>
                  <TableCell>{gw.ip_address || '\u2014'}</TableCell>
                  <TableCell>{gw.firmware_version || '\u2014'}</TableCell>
                  <TableCell align="right">
                    <Tooltip title="Edit">
                      <IconButton size="small" onClick={() => openEditDialog(gw)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton size="small" color="error" onClick={() => setDeleteTarget(gw)}>
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
        <DialogTitle>{editingId ? 'Edit Gateway' : 'Create Gateway'}</DialogTitle>
        <DialogContent>
          {error && dialogOpen && (
            <Alert severity="error" sx={{ mb: 2, mt: 1 }} onClose={() => setError(null)}>{error}</Alert>
          )}
          <TextField
            fullWidth required label="Gateway Code" value={form.gateway_code}
            onChange={(e) => setForm({ ...form, gateway_code: e.target.value })}
            sx={{ mt: 2, mb: 2 }} placeholder="e.g. GW-001"
          />
          <FormControl fullWidth required sx={{ mb: 2 }}>
            <InputLabel>Site</InputLabel>
            <Select
              value={form.site_id} label="Site"
              onChange={(e) => setForm({ ...form, site_id: e.target.value as string })}
            >
              {sites.map((site) => (
                <MenuItem key={site.id} value={site.id}>
                  {site.site_name} ({site.site_code})
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            fullWidth label="IP Address" value={form.ip_address}
            onChange={(e) => setForm({ ...form, ip_address: e.target.value })}
            sx={{ mb: 2 }} placeholder="e.g. 192.168.1.100"
          />
          <TextField
            fullWidth label="Firmware Version" value={form.firmware_version}
            onChange={(e) => setForm({ ...form, firmware_version: e.target.value })}
            placeholder="e.g. v2.1.0"
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => { setDialogOpen(false); setError(null); }}>Cancel</Button>
          <Button
            variant="contained" onClick={handleSubmit}
            disabled={submitting || !form.gateway_code || !form.site_id}
          >
            {submitting ? 'Saving...' : editingId ? 'Update Gateway' : 'Create Gateway'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirm Dialog */}
      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Gateway"
        message={`Are you sure you want to delete gateway "${deleteTarget?.gateway_code}"? This action cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </Container>
  );
}
