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
  CircularProgress
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { getSensors, createSensor } from '../../../api/client';
import apiClient from '../../../api/client';
import { Sensor } from '../../../api/types';
import { useTenantContext } from '../../../contexts/TenantContext';

interface Asset {
  id: string;
  asset_code: string;
  asset_name: string;
}

const EMPTY_FORM = {
  sensor_code: '',
  sensor_type: 'pump',
  asset_id: '',
  mount_location: '',
  mqtt_topic: ''
};

export default function SensorsPage() {
  const { tenantVersion } = useTenantContext();
  const [sensors, setSensors] = useState<Sensor[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);

  const fetchData = async () => {
    try {
      const [sensorList, assetsRes] = await Promise.all([
        getSensors(),
        apiClient.get('/assets'),
      ]);
      setSensors(Array.isArray(sensorList) ? sensorList : []);
      const assetData = assetsRes.data;
      setAssets(Array.isArray(assetData) ? assetData : []);
    } catch (err: any) {
      console.error('Failed to load sensors:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [tenantVersion]);

  const handleSubmit = async () => {
    if (!form.sensor_code || !form.sensor_type || !form.asset_id) {
      setError('Sensor Code, Type, and Asset are required');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const payload: any = {
        sensor_code: form.sensor_code,
        sensor_type: form.sensor_type,
        asset_id: form.asset_id,
      };
      if (form.mount_location) payload.mount_location = form.mount_location;
      if (form.mqtt_topic) payload.mqtt_topic = form.mqtt_topic;

      await createSensor(payload);
      setSuccess(`Sensor "${form.sensor_code}" registered successfully`);
      setTimeout(() => setSuccess(null), 4000);
      setDialogOpen(false);
      setForm(EMPTY_FORM);
      await fetchData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to register sensor');
    } finally {
      setSubmitting(false);
    }
  };

  // Helper to find asset name by id
  const getAssetName = (assetId: string) => {
    const asset = assets.find((a) => a.id === assetId);
    return asset ? `${asset.asset_name} (${asset.asset_code})` : assetId;
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
        <Typography variant="h4">Sensors</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setDialogOpen(true)}>
          Add Sensor
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
              <TableCell><strong>Sensor Code</strong></TableCell>
              <TableCell><strong>Type</strong></TableCell>
              <TableCell><strong>Asset</strong></TableCell>
              <TableCell><strong>Location</strong></TableCell>
              <TableCell><strong>MQTT Topic</strong></TableCell>
              <TableCell><strong>Status</strong></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {sensors.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  <Typography variant="body2" color="text.secondary" sx={{ py: 4 }}>
                    No sensors registered. Click "Add Sensor" to get started.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              sensors.map((sensor) => (
                <TableRow key={sensor.id} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                      {sensor.sensor_code}
                    </Typography>
                  </TableCell>
                  <TableCell><Chip label={sensor.sensor_type} size="small" variant="outlined" /></TableCell>
                  <TableCell>{getAssetName(sensor.asset_id)}</TableCell>
                  <TableCell>{sensor.mount_location || '\u2014'}</TableCell>
                  <TableCell>
                    <Chip label={sensor.mqtt_topic || '\u2014'} size="small" sx={{ fontFamily: 'monospace' }} />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={sensor.is_active ? 'active' : 'inactive'}
                      size="small"
                      color={sensor.is_active ? 'success' : 'default'}
                    />
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Register New Sensor</DialogTitle>
        <DialogContent>
          {error && dialogOpen && (
            <Alert severity="error" sx={{ mb: 2, mt: 1 }} onClose={() => setError(null)}>{error}</Alert>
          )}
          <TextField
            fullWidth required label="Sensor Code"
            value={form.sensor_code}
            onChange={(e) => setForm({ ...form, sensor_code: e.target.value })}
            sx={{ mt: 2, mb: 2 }}
            placeholder="e.g. pump_02"
            helperText="Unique identifier for this sensor"
          />
          <FormControl fullWidth sx={{ mb: 2 }} required>
            <InputLabel>Asset</InputLabel>
            <Select value={form.asset_id} label="Asset" onChange={(e) => setForm({ ...form, asset_id: e.target.value })}>
              {assets.map((a) => (
                <MenuItem key={a.id} value={a.id}>{a.asset_name} ({a.asset_code})</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Type</InputLabel>
            <Select value={form.sensor_type} label="Type" onChange={(e) => setForm({ ...form, sensor_type: e.target.value })}>
              <MenuItem value="pump">Pump</MenuItem>
              <MenuItem value="motor">Motor</MenuItem>
              <MenuItem value="compressor">Compressor</MenuItem>
              <MenuItem value="temperature">Temperature</MenuItem>
              <MenuItem value="vibration">Vibration</MenuItem>
              <MenuItem value="pressure">Pressure</MenuItem>
              <MenuItem value="other">Other</MenuItem>
            </Select>
          </FormControl>
          <TextField
            fullWidth label="Mount Location"
            value={form.mount_location}
            onChange={(e) => setForm({ ...form, mount_location: e.target.value })}
            sx={{ mb: 2 }}
            placeholder="e.g. Drive End"
          />
          <TextField
            fullWidth label="MQTT Topic (optional)"
            value={form.mqtt_topic}
            onChange={(e) => setForm({ ...form, mqtt_topic: e.target.value })}
            placeholder="Auto-derived if left empty"
            helperText="Leave empty to auto-derive from tenant/site/sensor hierarchy"
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => { setDialogOpen(false); setError(null); }}>Cancel</Button>
          <Button variant="contained" onClick={handleSubmit} disabled={submitting || !form.sensor_code || !form.asset_id}>
            {submitting ? 'Registering...' : 'Register Sensor'}
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
