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
  Chip,
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
  IconButton
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import apiClient from '../../../api/client';
import { useTenantContext } from '../../../contexts/TenantContext';

interface WorkOrder {
  id: string;
  title: string;
  description: string;
  priority: string;
  status: string;
  assigned_to?: string;
  related_event_id?: string;
  created_at: string;
  updated_at?: string;
}

interface WorkOrderForm {
  title: string;
  description: string;
  priority: string;
  status: string;
  assigned_to: string;
  related_event_id: string;
}

const EMPTY_FORM: WorkOrderForm = {
  title: '',
  description: '',
  priority: 'medium',
  status: 'open',
  assigned_to: '',
  related_event_id: '',
};

const PRIORITY_COLORS: Record<string, 'error' | 'warning' | 'info' | 'success' | 'default'> = {
  critical: 'error',
  high: 'warning',
  medium: 'info',
  low: 'success',
};

const STATUS_COLORS: Record<string, 'warning' | 'info' | 'success' | 'default'> = {
  open: 'warning',
  in_progress: 'info',
  completed: 'success',
  cancelled: 'default',
};

const STATUS_LABELS: Record<string, string> = {
  open: 'Open',
  in_progress: 'In Progress',
  completed: 'Completed',
  cancelled: 'Cancelled',
};

export default function WorkOrdersPage() {
  const { tenantVersion } = useTenantContext();
  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState<WorkOrderForm>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);

  const fetchWorkOrders = async () => {
    try {
      const { data } = await apiClient.get('/alerts/work-orders');
      setWorkOrders(Array.isArray(data) ? data : data.work_orders || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load work orders');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkOrders();
  }, [tenantVersion]);

  const openCreateDialog = () => {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setError(null);
    setDialogOpen(true);
  };

  const openEditDialog = (wo: WorkOrder) => {
    setForm({
      title: wo.title,
      description: wo.description || '',
      priority: wo.priority,
      status: wo.status,
      assigned_to: wo.assigned_to || '',
      related_event_id: wo.related_event_id || '',
    });
    setEditingId(wo.id);
    setError(null);
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    if (!form.title) {
      setError('Title is required');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const payload: Record<string, any> = {
        title: form.title,
        description: form.description,
        priority: form.priority,
        status: form.status,
      };
      if (form.assigned_to) payload.assigned_to = form.assigned_to;
      if (form.related_event_id) payload.related_event_id = form.related_event_id;

      if (editingId) {
        await apiClient.patch(`/alerts/work-orders/${editingId}`, payload);
        setSuccess(`Work order "${form.title}" updated successfully`);
      } else {
        await apiClient.post('/alerts/work-orders', payload);
        setSuccess(`Work order "${form.title}" created successfully`);
      }
      setTimeout(() => setSuccess(null), 4000);
      setDialogOpen(false);
      setForm(EMPTY_FORM);
      setEditingId(null);
      await fetchWorkOrders();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save work order');
    } finally {
      setSubmitting(false);
    }
  };

  const handleStatusChange = async (woId: string, newStatus: string) => {
    try {
      await apiClient.patch(`/alerts/work-orders/${woId}`, { status: newStatus });
      setSuccess('Status updated successfully');
      setTimeout(() => setSuccess(null), 4000);
      await fetchWorkOrders();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update status');
    }
  };

  const formatTime = (iso: string) => {
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
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
        <Typography variant="h4">Work Orders</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreateDialog}>
          Create Work Order
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
              <TableCell><strong>Title</strong></TableCell>
              <TableCell><strong>Priority</strong></TableCell>
              <TableCell><strong>Status</strong></TableCell>
              <TableCell><strong>Assigned To</strong></TableCell>
              <TableCell><strong>Created At</strong></TableCell>
              <TableCell><strong>Actions</strong></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {workOrders.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  <Typography variant="body2" color="text.secondary" sx={{ py: 4 }}>
                    No work orders found. Click "Create Work Order" to get started.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              workOrders.map((wo) => (
                <TableRow key={wo.id} hover>
                  <TableCell>
                    <Typography variant="body2" fontWeight={600}>{wo.title}</Typography>
                    {wo.description && (
                      <Typography variant="caption" color="text.secondary" display="block" noWrap sx={{ maxWidth: 250 }} title={wo.description}>
                        {wo.description}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={wo.priority}
                      size="small"
                      color={PRIORITY_COLORS[wo.priority] || 'default'}
                    />
                  </TableCell>
                  <TableCell>
                    <FormControl size="small" variant="standard" sx={{ minWidth: 120 }}>
                      <Select
                        value={wo.status}
                        onChange={(e) => handleStatusChange(wo.id, e.target.value)}
                        renderValue={(value) => (
                          <Chip
                            label={STATUS_LABELS[value] || value}
                            size="small"
                            color={STATUS_COLORS[value] || 'default'}
                          />
                        )}
                      >
                        <MenuItem value="open">Open</MenuItem>
                        <MenuItem value="in_progress">In Progress</MenuItem>
                        <MenuItem value="completed">Completed</MenuItem>
                        <MenuItem value="cancelled">Cancelled</MenuItem>
                      </Select>
                    </FormControl>
                  </TableCell>
                  <TableCell>{wo.assigned_to || '\u2014'}</TableCell>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>
                    {formatTime(wo.created_at)}
                  </TableCell>
                  <TableCell>
                    <IconButton size="small" onClick={() => openEditDialog(wo)} title="Edit">
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editingId ? 'Edit Work Order' : 'Create Work Order'}</DialogTitle>
        <DialogContent>
          {error && dialogOpen && (
            <Alert severity="error" sx={{ mb: 2, mt: 1 }} onClose={() => setError(null)}>{error}</Alert>
          )}
          <TextField
            fullWidth
            required
            label="Title"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            sx={{ mt: 2, mb: 2 }}
            placeholder="e.g. Replace Pump Bearing"
          />
          <TextField
            fullWidth
            label="Description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            sx={{ mb: 2 }}
            multiline
            rows={3}
            placeholder="Detailed description of the work to be done"
          />
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Priority</InputLabel>
            <Select
              value={form.priority}
              label="Priority"
              onChange={(e) => setForm({ ...form, priority: e.target.value })}
            >
              <MenuItem value="critical">Critical</MenuItem>
              <MenuItem value="high">High</MenuItem>
              <MenuItem value="medium">Medium</MenuItem>
              <MenuItem value="low">Low</MenuItem>
            </Select>
          </FormControl>
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Status</InputLabel>
            <Select
              value={form.status}
              label="Status"
              onChange={(e) => setForm({ ...form, status: e.target.value })}
            >
              <MenuItem value="open">Open</MenuItem>
              <MenuItem value="in_progress">In Progress</MenuItem>
              <MenuItem value="completed">Completed</MenuItem>
              <MenuItem value="cancelled">Cancelled</MenuItem>
            </Select>
          </FormControl>
          <TextField
            fullWidth
            label="Assigned To"
            value={form.assigned_to}
            onChange={(e) => setForm({ ...form, assigned_to: e.target.value })}
            sx={{ mb: 2 }}
            placeholder="e.g. John Smith"
          />
          <TextField
            fullWidth
            label="Related Event ID (optional)"
            value={form.related_event_id}
            onChange={(e) => setForm({ ...form, related_event_id: e.target.value })}
            placeholder="Link to an alarm event"
            helperText="Optional: associate this work order with a specific alarm event"
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => { setDialogOpen(false); setError(null); }}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleSubmit}
            disabled={submitting || !form.title}
          >
            {submitting ? 'Saving...' : editingId ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
