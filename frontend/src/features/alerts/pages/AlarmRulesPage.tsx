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
  Switch,
  FormControlLabel,
  IconButton
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import apiClient from '../../../api/client';
import { useTenantContext } from '../../../contexts/TenantContext';

interface AlarmRule {
  id: string;
  rule_name: string;
  condition_type: string;
  condition_value: string;
  severity: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

interface RuleForm {
  rule_name: string;
  condition_type: string;
  condition_value: string;
  severity: string;
  is_active: boolean;
}

const EMPTY_FORM: RuleForm = {
  rule_name: '',
  condition_type: 'threshold',
  condition_value: '',
  severity: 'warning',
  is_active: true,
};

const SEVERITY_COLORS: Record<string, 'error' | 'warning' | 'info' | 'default'> = {
  critical: 'error',
  warning: 'warning',
  info: 'info',
};

export default function AlarmRulesPage() {
  const { tenantVersion } = useTenantContext();
  const [rules, setRules] = useState<AlarmRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState<RuleForm>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchRules = async () => {
    try {
      const { data } = await apiClient.get('/alerts/rules');
      setRules(Array.isArray(data) ? data : data.rules || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load alarm rules');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRules();
  }, [tenantVersion]);

  const openCreateDialog = () => {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setError(null);
    setDialogOpen(true);
  };

  const openEditDialog = (rule: AlarmRule) => {
    setForm({
      rule_name: rule.rule_name,
      condition_type: rule.condition_type,
      condition_value: rule.condition_value,
      severity: rule.severity,
      is_active: rule.is_active,
    });
    setEditingId(rule.id);
    setError(null);
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    if (!form.rule_name || !form.condition_value) {
      setError('Rule Name and Condition Value are required');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      if (editingId) {
        await apiClient.patch(`/alerts/rules/${editingId}`, form);
        setSuccess(`Rule "${form.rule_name}" updated successfully`);
      } else {
        await apiClient.post('/alerts/rules', form);
        setSuccess(`Rule "${form.rule_name}" created successfully`);
      }
      setTimeout(() => setSuccess(null), 4000);
      setDialogOpen(false);
      setForm(EMPTY_FORM);
      setEditingId(null);
      await fetchRules();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save rule');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deletingId) return;
    setSubmitting(true);
    try {
      await apiClient.delete(`/alerts/rules/${deletingId}`);
      setSuccess('Rule deleted successfully');
      setTimeout(() => setSuccess(null), 4000);
      setDeleteDialogOpen(false);
      setDeletingId(null);
      await fetchRules();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete rule');
      setDeleteDialogOpen(false);
    } finally {
      setSubmitting(false);
    }
  };

  const confirmDelete = (id: string) => {
    setDeletingId(id);
    setDeleteDialogOpen(true);
  };

  const formatCondition = (rule: AlarmRule) => {
    const typeLabels: Record<string, string> = {
      threshold: 'Threshold',
      anomaly_score: 'Anomaly Score',
      fault_class: 'Fault Class',
    };
    return `${typeLabels[rule.condition_type] || rule.condition_type}: ${rule.condition_value}`;
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
        <Typography variant="h4">Alarm Rules</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreateDialog}>
          Create Rule
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
              <TableCell><strong>Rule Name</strong></TableCell>
              <TableCell><strong>Condition</strong></TableCell>
              <TableCell><strong>Severity</strong></TableCell>
              <TableCell><strong>Status</strong></TableCell>
              <TableCell><strong>Actions</strong></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rules.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} align="center">
                  <Typography variant="body2" color="text.secondary" sx={{ py: 4 }}>
                    No alarm rules configured. Click "Create Rule" to get started.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              rules.map((rule) => (
                <TableRow key={rule.id} hover>
                  <TableCell>{rule.rule_name}</TableCell>
                  <TableCell>{formatCondition(rule)}</TableCell>
                  <TableCell>
                    <Chip
                      label={rule.severity}
                      size="small"
                      color={SEVERITY_COLORS[rule.severity] || 'default'}
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={rule.is_active ? 'Active' : 'Inactive'}
                      size="small"
                      color={rule.is_active ? 'success' : 'default'}
                      variant={rule.is_active ? 'filled' : 'outlined'}
                    />
                  </TableCell>
                  <TableCell>
                    <IconButton size="small" onClick={() => openEditDialog(rule)} title="Edit">
                      <EditIcon fontSize="small" />
                    </IconButton>
                    <IconButton size="small" onClick={() => confirmDelete(rule.id)} title="Delete" color="error">
                      <DeleteIcon fontSize="small" />
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
        <DialogTitle>{editingId ? 'Edit Rule' : 'Create Alarm Rule'}</DialogTitle>
        <DialogContent>
          {error && dialogOpen && (
            <Alert severity="error" sx={{ mb: 2, mt: 1 }} onClose={() => setError(null)}>{error}</Alert>
          )}
          <TextField
            fullWidth
            required
            label="Rule Name"
            value={form.rule_name}
            onChange={(e) => setForm({ ...form, rule_name: e.target.value })}
            sx={{ mt: 2, mb: 2 }}
            placeholder="e.g. High Temperature Alert"
          />
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Condition Type</InputLabel>
            <Select
              value={form.condition_type}
              label="Condition Type"
              onChange={(e) => setForm({ ...form, condition_type: e.target.value })}
            >
              <MenuItem value="threshold">Threshold</MenuItem>
              <MenuItem value="anomaly_score">Anomaly Score</MenuItem>
              <MenuItem value="fault_class">Fault Class</MenuItem>
            </Select>
          </FormControl>
          <TextField
            fullWidth
            required
            label="Condition Value"
            value={form.condition_value}
            onChange={(e) => setForm({ ...form, condition_value: e.target.value })}
            sx={{ mb: 2 }}
            placeholder="e.g. > 85.0"
            helperText="The threshold value or pattern to match"
          />
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Severity</InputLabel>
            <Select
              value={form.severity}
              label="Severity"
              onChange={(e) => setForm({ ...form, severity: e.target.value })}
            >
              <MenuItem value="critical">Critical</MenuItem>
              <MenuItem value="warning">Warning</MenuItem>
              <MenuItem value="info">Info</MenuItem>
            </Select>
          </FormControl>
          <FormControlLabel
            control={
              <Switch
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              />
            }
            label="Active"
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => { setDialogOpen(false); setError(null); }}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleSubmit}
            disabled={submitting || !form.rule_name || !form.condition_value}
          >
            {submitting ? 'Saving...' : editingId ? 'Update Rule' : 'Create Rule'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Delete Rule</DialogTitle>
        <DialogContent>
          <Typography>Are you sure you want to delete this alarm rule? This action cannot be undone.</Typography>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" color="error" onClick={handleDelete} disabled={submitting}>
            {submitting ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
