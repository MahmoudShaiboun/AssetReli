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
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useNavigate } from 'react-router-dom';
import apiClient from '../../../api/client';
import ConfirmDialog from '../../../components/ConfirmDialog';
import { useTenantContext } from '../../../contexts/TenantContext';

interface Site {
  id: string;
  site_code: string;
  site_name: string;
}

interface Asset {
  id: string;
  asset_code: string;
  asset_name: string;
  site_id: string;
  asset_type?: string;
  manufacturer?: string;
  model_number?: string;
}

const EMPTY_FORM = {
  asset_code: '',
  asset_name: '',
  site_id: '',
  asset_type: '',
  manufacturer: '',
  model_number: '',
};

export default function AssetsPage() {
  const { tenantVersion } = useTenantContext();
  const navigate = useNavigate();
  const [assets, setAssets] = useState<Asset[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Asset | null>(null);

  const fetchSites = async () => {
    try {
      const { data } = await apiClient.get('/sites');
      setSites(Array.isArray(data) ? data : data.sites || []);
    } catch (err: any) {
      console.error('Failed to load sites:', err);
    }
  };

  const fetchAssets = async () => {
    try {
      const { data } = await apiClient.get('/assets');
      setAssets(Array.isArray(data) ? data : data.assets || []);
    } catch (err: any) {
      console.error('Failed to load assets:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSites();
    fetchAssets();
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

  const openEditDialog = (asset: Asset) => {
    setEditingId(asset.id);
    setForm({
      asset_code: asset.asset_code,
      asset_name: asset.asset_name,
      site_id: asset.site_id,
      asset_type: asset.asset_type || '',
      manufacturer: asset.manufacturer || '',
      model_number: asset.model_number || '',
    });
    setError(null);
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    if (!form.asset_code || !form.asset_name || !form.site_id) {
      setError('Asset Code, Asset Name, and Site are required');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const payload: Record<string, string> = {
        asset_code: form.asset_code,
        asset_name: form.asset_name,
        site_id: form.site_id,
      };
      if (form.asset_type) payload.asset_type = form.asset_type;
      if (form.manufacturer) payload.manufacturer = form.manufacturer;
      if (form.model_number) payload.model_number = form.model_number;

      if (editingId) {
        await apiClient.patch(`/assets/${editingId}`, payload);
        setSuccess(`Asset "${form.asset_code}" updated successfully`);
      } else {
        await apiClient.post('/assets', payload);
        setSuccess(`Asset "${form.asset_code}" created successfully`);
      }

      setTimeout(() => setSuccess(null), 4000);
      setDialogOpen(false);
      setForm(EMPTY_FORM);
      setEditingId(null);
      await fetchAssets();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save asset');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;

    try {
      await apiClient.delete(`/assets/${deleteTarget.id}`);
      setSuccess(`Asset "${deleteTarget.asset_code}" deleted successfully`);
      setTimeout(() => setSuccess(null), 4000);
      setDeleteTarget(null);
      await fetchAssets();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete asset');
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
        <Typography variant="h4">Assets</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreateDialog}>
          Add Asset
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
              <TableCell><strong>Asset Code</strong></TableCell>
              <TableCell><strong>Asset Name</strong></TableCell>
              <TableCell><strong>Site</strong></TableCell>
              <TableCell><strong>Type</strong></TableCell>
              <TableCell><strong>Manufacturer</strong></TableCell>
              <TableCell align="right"><strong>Actions</strong></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {assets.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  <Typography variant="body2" color="text.secondary" sx={{ py: 4 }}>
                    No assets configured. Click "Add Asset" to get started.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              assets.map((asset) => (
                <TableRow key={asset.id} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                      {asset.asset_code}
                    </Typography>
                  </TableCell>
                  <TableCell>{asset.asset_name}</TableCell>
                  <TableCell>{getSiteName(asset.site_id)}</TableCell>
                  <TableCell>{asset.asset_type || '\u2014'}</TableCell>
                  <TableCell>{asset.manufacturer || '\u2014'}</TableCell>
                  <TableCell align="right">
                    <Tooltip title="View Details">
                      <IconButton size="small" onClick={() => navigate(`/assets/${asset.id}`)}>
                        <VisibilityIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Edit">
                      <IconButton size="small" onClick={() => openEditDialog(asset)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton size="small" color="error" onClick={() => setDeleteTarget(asset)}>
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
        <DialogTitle>{editingId ? 'Edit Asset' : 'Create Asset'}</DialogTitle>
        <DialogContent>
          {error && dialogOpen && (
            <Alert severity="error" sx={{ mb: 2, mt: 1 }} onClose={() => setError(null)}>{error}</Alert>
          )}
          <TextField
            fullWidth required label="Asset Code" value={form.asset_code}
            onChange={(e) => setForm({ ...form, asset_code: e.target.value })}
            sx={{ mt: 2, mb: 2 }} placeholder="e.g. PUMP-001"
          />
          <TextField
            fullWidth required label="Asset Name" value={form.asset_name}
            onChange={(e) => setForm({ ...form, asset_name: e.target.value })}
            sx={{ mb: 2 }} placeholder="e.g. Main Cooling Pump"
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
            fullWidth label="Asset Type" value={form.asset_type}
            onChange={(e) => setForm({ ...form, asset_type: e.target.value })}
            sx={{ mb: 2 }} placeholder="e.g. Pump, Motor, Compressor"
          />
          <TextField
            fullWidth label="Manufacturer" value={form.manufacturer}
            onChange={(e) => setForm({ ...form, manufacturer: e.target.value })}
            sx={{ mb: 2 }} placeholder="e.g. Siemens"
          />
          <TextField
            fullWidth label="Model Number" value={form.model_number}
            onChange={(e) => setForm({ ...form, model_number: e.target.value })}
            placeholder="e.g. XYZ-1234"
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => { setDialogOpen(false); setError(null); }}>Cancel</Button>
          <Button
            variant="contained" onClick={handleSubmit}
            disabled={submitting || !form.asset_code || !form.asset_name || !form.site_id}
          >
            {submitting ? 'Saving...' : editingId ? 'Update Asset' : 'Create Asset'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirm Dialog */}
      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Asset"
        message={`Are you sure you want to delete asset "${deleteTarget?.asset_code}"? This action cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </Container>
  );
}
