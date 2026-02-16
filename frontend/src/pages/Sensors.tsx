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
import { getSensors, createSensor } from '../services/api';

interface Sensor {
  _id: string;
  sensor_id: string;
  name: string;
  type: string;
  location?: string;
  features?: string[];
  mqtt_topic?: string;
  status?: string;
}

const EMPTY_FORM = {
  sensor_id: '',
  name: '',
  type: 'pump',
  location: '',
  mqtt_topic: ''
};

export default function Sensors() {
  const [sensors, setSensors] = useState<Sensor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);

  const fetchSensors = async () => {
    try {
      const data = await getSensors();
      setSensors(data.sensors || []);
    } catch (err: any) {
      console.error('Failed to load sensors:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSensors();
    const interval = setInterval(fetchSensors, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleSubmit = async () => {
    if (!form.sensor_id || !form.name || !form.type) {
      setError('Sensor ID, Name, and Type are required');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const payload: any = {
        sensor_id: form.sensor_id,
        name: form.name,
        type: form.type
      };
      if (form.location) payload.location = form.location;
      if (form.mqtt_topic) payload.mqtt_topic = form.mqtt_topic;

      await createSensor(payload);
      setSuccess(`Sensor "${form.sensor_id}" registered successfully`);
      setTimeout(() => setSuccess(null), 4000);
      setDialogOpen(false);
      setForm(EMPTY_FORM);
      await fetchSensors();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to register sensor');
    } finally {
      setSubmitting(false);
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
        <Typography variant="h4">Sensors</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setDialogOpen(true)}
        >
          Add Sensor
        </Button>
      </Box>

      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
          {success}
        </Alert>
      )}

      {error && !dialogOpen && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell><strong>Sensor ID</strong></TableCell>
              <TableCell><strong>Name</strong></TableCell>
              <TableCell><strong>Type</strong></TableCell>
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
                <TableRow key={sensor._id} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                      {sensor.sensor_id}
                    </Typography>
                  </TableCell>
                  <TableCell>{sensor.name}</TableCell>
                  <TableCell>
                    <Chip label={sensor.type} size="small" variant="outlined" />
                  </TableCell>
                  <TableCell>{sensor.location || '—'}</TableCell>
                  <TableCell>
                    <Chip
                      label={sensor.mqtt_topic || `sensors/${sensor.sensor_id}`}
                      size="small"
                      sx={{ fontFamily: 'monospace' }}
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={sensor.status || 'active'}
                      size="small"
                      color={sensor.status === 'active' || !sensor.status ? 'success' : 'default'}
                    />
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Add Sensor Dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Register New Sensor</DialogTitle>
        <DialogContent>
          {error && dialogOpen && (
            <Alert severity="error" sx={{ mb: 2, mt: 1 }} onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          <TextField
            fullWidth
            required
            label="Sensor ID"
            value={form.sensor_id}
            onChange={(e) => setForm({ ...form, sensor_id: e.target.value })}
            sx={{ mt: 2, mb: 2 }}
            placeholder="e.g. pump_02"
            helperText={form.sensor_id ? `MQTT topic: sensors/${form.sensor_id}` : 'Unique identifier for this sensor'}
          />

          <TextField
            fullWidth
            required
            label="Name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            sx={{ mb: 2 }}
            placeholder="e.g. Main Pump 2"
          />

          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Type</InputLabel>
            <Select
              value={form.type}
              label="Type"
              onChange={(e) => setForm({ ...form, type: e.target.value })}
            >
              <MenuItem value="pump">Pump</MenuItem>
              <MenuItem value="motor">Motor</MenuItem>
              <MenuItem value="compressor">Compressor</MenuItem>
              <MenuItem value="other">Other</MenuItem>
            </Select>
          </FormControl>

          <TextField
            fullWidth
            label="Location"
            value={form.location}
            onChange={(e) => setForm({ ...form, location: e.target.value })}
            sx={{ mb: 2 }}
            placeholder="e.g. Building A"
          />

          <TextField
            fullWidth
            label="MQTT Topic (optional)"
            value={form.mqtt_topic}
            onChange={(e) => setForm({ ...form, mqtt_topic: e.target.value })}
            placeholder={form.sensor_id ? `sensors/${form.sensor_id}` : 'sensors/{sensor_id}'}
            helperText="Leave empty to auto-derive from Sensor ID"
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => { setDialogOpen(false); setError(null); }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSubmit}
            disabled={submitting || !form.sensor_id || !form.name}
          >
            {submitting ? 'Registering...' : 'Register Sensor'}
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
