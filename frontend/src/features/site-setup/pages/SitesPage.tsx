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
  address?: string;
  city?: string;
  country?: string;
  timezone: string;
}

const EMPTY_FORM = {
  site_code: '',
  site_name: '',
  address: '',
  city: '',
  country: '',
  timezone: 'UTC',
};

export default function SitesPage() {
  const { tenantVersion } = useTenantContext();
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Site | null>(null);

  const fetchSites = async () => {
    try {
      const { data } = await apiClient.get('/sites');
      setSites(Array.isArray(data) ? data : data.sites || []);
    } catch (err: any) {
      console.error('Failed to load sites:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSites();
  }, [tenantVersion]);

  const openCreateDialog = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setError(null);
    setDialogOpen(true);
  };

  const openEditDialog = (site: Site) => {
    setEditingId(site.id);
    setForm({
      site_code: site.site_code,
      site_name: site.site_name,
      address: site.address || '',
      city: site.city || '',
      country: site.country || '',
      timezone: site.timezone || 'UTC',
    });
    setError(null);
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    if (!form.site_code || !form.site_name) {
      setError('Site Code and Site Name are required');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const payload: Record<string, string> = {
        site_code: form.site_code,
        site_name: form.site_name,
        timezone: form.timezone || 'UTC',
      };
      if (form.address) payload.address = form.address;
      if (form.city) payload.city = form.city;
      if (form.country) payload.country = form.country;

      if (editingId) {
        await apiClient.patch(`/sites/${editingId}`, payload);
        setSuccess(`Site "${form.site_code}" updated successfully`);
      } else {
        await apiClient.post('/sites', payload);
        setSuccess(`Site "${form.site_code}" created successfully`);
      }

      setTimeout(() => setSuccess(null), 4000);
      setDialogOpen(false);
      setForm(EMPTY_FORM);
      setEditingId(null);
      await fetchSites();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save site');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;

    try {
      await apiClient.delete(`/sites/${deleteTarget.id}`);
      setSuccess(`Site "${deleteTarget.site_code}" deleted successfully`);
      setTimeout(() => setSuccess(null), 4000);
      setDeleteTarget(null);
      await fetchSites();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete site');
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
        <Typography variant="h4">Sites</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreateDialog}>
          Add Site
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
              <TableCell><strong>Site Code</strong></TableCell>
              <TableCell><strong>Site Name</strong></TableCell>
              <TableCell><strong>City</strong></TableCell>
              <TableCell><strong>Country</strong></TableCell>
              <TableCell><strong>Timezone</strong></TableCell>
              <TableCell align="right"><strong>Actions</strong></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {sites.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  <Typography variant="body2" color="text.secondary" sx={{ py: 4 }}>
                    No sites configured. Click "Add Site" to get started.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              sites.map((site) => (
                <TableRow key={site.id} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                      {site.site_code}
                    </Typography>
                  </TableCell>
                  <TableCell>{site.site_name}</TableCell>
                  <TableCell>{site.city || '\u2014'}</TableCell>
                  <TableCell>{site.country || '\u2014'}</TableCell>
                  <TableCell>{site.timezone}</TableCell>
                  <TableCell align="right">
                    <Tooltip title="Edit">
                      <IconButton size="small" onClick={() => openEditDialog(site)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton size="small" color="error" onClick={() => setDeleteTarget(site)}>
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
        <DialogTitle>{editingId ? 'Edit Site' : 'Create Site'}</DialogTitle>
        <DialogContent>
          {error && dialogOpen && (
            <Alert severity="error" sx={{ mb: 2, mt: 1 }} onClose={() => setError(null)}>{error}</Alert>
          )}
          <TextField
            fullWidth required label="Site Code" value={form.site_code}
            onChange={(e) => setForm({ ...form, site_code: e.target.value })}
            sx={{ mt: 2, mb: 2 }} placeholder="e.g. SITE-001"
          />
          <TextField
            fullWidth required label="Site Name" value={form.site_name}
            onChange={(e) => setForm({ ...form, site_name: e.target.value })}
            sx={{ mb: 2 }} placeholder="e.g. Main Factory"
          />
          <TextField
            fullWidth label="Address" value={form.address}
            onChange={(e) => setForm({ ...form, address: e.target.value })}
            sx={{ mb: 2 }} placeholder="e.g. 123 Industrial Ave"
          />
          <TextField
            fullWidth label="City" value={form.city}
            onChange={(e) => setForm({ ...form, city: e.target.value })}
            sx={{ mb: 2 }} placeholder="e.g. Houston"
          />
          <TextField
            fullWidth label="Country" value={form.country}
            onChange={(e) => setForm({ ...form, country: e.target.value })}
            sx={{ mb: 2 }} placeholder="e.g. USA"
          />
          <TextField
            fullWidth label="Timezone" value={form.timezone}
            onChange={(e) => setForm({ ...form, timezone: e.target.value })}
            placeholder="UTC" helperText="IANA timezone (e.g. America/Chicago)"
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => { setDialogOpen(false); setError(null); }}>Cancel</Button>
          <Button
            variant="contained" onClick={handleSubmit}
            disabled={submitting || !form.site_code || !form.site_name}
          >
            {submitting ? 'Saving...' : editingId ? 'Update Site' : 'Create Site'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirm Dialog */}
      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Site"
        message={`Are you sure you want to delete site "${deleteTarget?.site_code}"? This action cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </Container>
  );
}
